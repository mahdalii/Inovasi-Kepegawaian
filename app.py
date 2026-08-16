import io
import mimetypes
import os
import datetime
import uuid

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from supabase import create_client

import config

VALID_JENIS = {"tahunan", "sakit", "alasan_penting"}

VALID_UPTD = {
    "bidang_sekretariat", "bidang_pendapatan",
    "bidang_pengembangan_pendapatan", "bidang_pengendalian_pengawasan",
    "batam_centre", "batuaji", "tanjungpinang", "bintan", "kijang",
    "natuna", "anambas", "karimun", "tanjungbatu", "lingga"
}

UPTD_LABEL = {
    "bidang_sekretariat": "Bidang Sekretariat",
    "bidang_pendapatan": "Bidang Pendapatan",
    "bidang_pengembangan_pendapatan": "Bidang Pengembangan Pendapatan",
    "bidang_pengendalian_pengawasan": "Bidang Pengendalian dan Pengawasan",
    "batam_centre": "Batam Centre",
    "batuaji": "Batuaji",
    "tanjungpinang": "Tanjungpinang",
    "bintan": "Bintan",
    "kijang": "Kijang",
    "natuna": "Natuna",
    "anambas": "Anambas",
    "karimun": "Karimun",
    "tanjungbatu": "Tanjungbatu",
    "lingga": "Lingga",
}


def is_late(status, tgl_masuk, today=None):
    if status not in {"Baru", "Diproses"}:
        return False
    tgl = datetime.date.fromisoformat(tgl_masuk)
    today = today or datetime.date.today()
    return (today - tgl).days > 2


STATUS_ORDER = {"Baru": 1, "Diproses": 2, "Disetujui": 3, "Ditolak": 3}


def can_transition(current, new):
    return STATUS_ORDER.get(new, 0) > STATUS_ORDER.get(current, 99)


def validate_form(nama, uptd, jenis, tgl_mulai, tgl_selesai, berkas_ok, file_size_ok):
    errors = []
    if not nama.strip():
        errors.append("Nama wajib diisi")
    if not uptd.strip():
        errors.append("Tempat kerja wajib diisi")
    elif uptd not in VALID_UPTD:
        errors.append("Tempat kerja tidak valid")
    if jenis not in VALID_JENIS:
        errors.append("Jenis cuti tidak valid")
    if not tgl_mulai or not tgl_selesai:
        errors.append("Tanggal mulai dan selesai wajib diisi")
    elif tgl_mulai > tgl_selesai:
        errors.append("Tanggal mulai tidak boleh lebih lama dari tanggal selesai")
    if not berkas_ok:
        errors.append("Berkas wajib diupload (PDF/JPG/PNG)")
    if not file_size_ok:
        errors.append("Ukuran berkas melebihi 5 MB")
    return errors


JENIS_LABEL = {"tahunan": "Cuti Tahunan", "sakit": "Cuti Sakit",
               "alasan_penting": "Cuti Alasan Penting"}

BERKAS_LABEL = {
    "tahunan": "Form persetujuan atasan (PDF/JPG/PNG)",
    "sakit": "Bukti sakit (PDF/JPG/PNG)",
    "alasan_penting": "Bukti alasan penting (PDF/JPG/PNG)",
}

allowed_ext = lambda name: name.rsplit(".", 1)[-1].lower() in config.ALLOWED_EXTENSIONS


def safe_filename(original):
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else "bin"
    return f"{uuid.uuid4().hex}.{ext}"


_client = None


def get_client():
    global _client
    if _client is None:
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY)
    return _client


def format_nomor(tahun, nilai):
    return f"CUT-{tahun}-{nilai:04d}"


def get_nomor_value(sb, tahun):
    row = sb.table("counter").select("*").eq("tahun", tahun).execute().data
    if row:
        nilai = row[0]["nilai"] + 1
        sb.table("counter").update({"nilai": nilai}).eq("tahun", tahun).execute()
    else:
        nilai = 1
        sb.table("counter").insert({"tahun": tahun, "nilai": nilai}).execute()
    return nilai
# ponytail: counter satu baris per tahun, lock lewat insert/update.
# Konkurensi tinggi bisa lompat nomor — upgrade ke sequence postgres kalau perlu.


def save_pengajuan(sb, nama, uptd, jenis, tgl_mulai, tgl_selesai, filename, tgl_masuk):
    tahun = tgl_masuk[:4]
    for _ in range(3):
        nilai = get_nomor_value(sb, tahun)
        nomor = format_nomor(tahun, nilai)
        try:
            sb.table("cuti").insert({
                "nomor": nomor, "nama": nama.strip(), "uptd": uptd.strip(),
                "jenis": jenis, "tgl_mulai": tgl_mulai, "tgl_selesai": tgl_selesai,
                "berkas": filename, "status": "Baru", "catatan": "", "tgl_masuk": tgl_masuk,
            }).execute()
            return nomor
        except Exception:
            continue
    raise RuntimeError("Gagal menyimpan pengajuan")


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    @app.route("/", methods=["GET", "POST"])
    def form_pegawai():
        if request.method == "POST":
            f = request.files.get("berkas")
            berkas_ok = f is not None and f.filename and allowed_ext(f.filename)
            size = None
            if f is not None:
                f.stream.seek(0, os.SEEK_END)
                size = f.stream.tell()
                f.stream.seek(0)
            size_ok = size is not None and size <= config.MAX_UPLOAD_MB * 1024 * 1024
            errors = validate_form(
                request.form.get("nama", ""), request.form.get("uptd", ""),
                request.form.get("jenis", ""), request.form.get("tgl_mulai", ""),
                request.form.get("tgl_selesai", ""), berkas_ok, size_ok,
            )
            if errors:
                return render_template("form.html", errors=errors,
                                       jenis_labels=JENIS_LABEL,
                                       berkas_labels=BERKAS_LABEL,
                                       uptd_labels=UPTD_LABEL,
                                       data=request.form), 400
            data = f.read()
            filename = safe_filename(f.filename)
            try:
                get_client().storage.from_(config.STORAGE_BUCKET).upload(filename, data)
            except Exception:
                errors = ["Gagal mengunggah berkas. Coba file lebih kecil (maks 4MB) atau coba lagi."]
                return render_template("form.html", errors=errors,
                                       jenis_labels=JENIS_LABEL, berkas_labels=BERKAS_LABEL,
                                       uptd_labels=UPTD_LABEL, data=request.form), 400
            try:
                nomor = save_pengajuan(get_client(),
                                       request.form["nama"], request.form["uptd"],
                                       request.form["jenis"], request.form["tgl_mulai"],
                                       request.form["tgl_selesai"], filename,
                                       datetime.date.today().isoformat())
            except Exception:
                get_client().storage.from_(config.STORAGE_BUCKET).remove([filename])
                errors = ["Gagal menyimpan pengajuan. Silakan coba lagi."]
                return render_template("form.html", errors=errors,
                                       jenis_labels=JENIS_LABEL, berkas_labels=BERKAS_LABEL,
                                       uptd_labels=UPTD_LABEL, data=request.form), 500
            return render_template("form.html", success=nomor,
                                   jenis_labels=JENIS_LABEL, berkas_labels=BERKAS_LABEL,
                                   uptd_labels=UPTD_LABEL)
        return render_template("form.html", jenis_labels=JENIS_LABEL,
                               berkas_labels=BERKAS_LABEL, uptd_labels=UPTD_LABEL)

    @app.route("/status", methods=["GET", "POST"])
    def status():
        q = request.form.get("q", "").strip()
        rows = []
        if request.method == "POST" and q:
            rows = get_client().table("cuti").select("*") \
                .or_(f"nomor.ilike.*{q}*,nama.ilike.*{q}*") \
                .order("tgl_masuk", desc=True).order("id", desc=True) \
                .execute().data
        return render_template("status.html", rows=rows, q=q,
                               jenis_labels=JENIS_LABEL, uptd_labels=UPTD_LABEL)

    from functools import wraps

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("staff"):
                return redirect(url_for("login"))
            return view(*args, **kwargs)
        return wrapped

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            if request.form.get("password") == config.STAFF_PASSWORD:
                session["staff"] = True
                return redirect(url_for("dashboard"))
            flash("Kata sandi salah", "error")
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.pop("staff", None)
        return redirect(url_for("login"))

    @app.route("/staff")
    @login_required
    def dashboard():
        q = request.args.get("q", "").strip()
        fstatus = request.args.get("status", "").strip()
        f_uptd = request.args.get("uptd", "").strip()
        b = get_client().table("cuti").select("*")
        if q:
            b = b.or_(f"nomor.ilike.*{q}*,nama.ilike.*{q}*")
        if fstatus:
            b = b.eq("status", fstatus)
        if f_uptd:
            b = b.eq("uptd", f_uptd)
        b = b.order("tgl_masuk", desc=True).order("id", desc=True)
        rows = b.execute().data
        today = datetime.date.today()
        late_ids = {r["id"] for r in rows if is_late(r["status"], r["tgl_masuk"], today)}
        return render_template("dashboard.html", rows=rows, late_ids=late_ids,
                               q=q, filter_status=fstatus, filter_uptd=f_uptd,
                               jenis_labels=JENIS_LABEL, uptd_labels=UPTD_LABEL,
                               uptds=list(UPTD_LABEL),
                               statuses=["Baru", "Diproses", "Disetujui", "Ditolak"])

    @app.route("/staff/<int:pengajuan_id>", methods=["GET", "POST"])
    @login_required
    def detail(pengajuan_id):
        sb = get_client()
        data = sb.table("cuti").select("*").eq("id", pengajuan_id).execute().data
        if not data:
            return redirect(url_for("dashboard"))
        row = data[0]
        if request.method == "POST":
            new_status = request.form.get("status", "")
            catatan = request.form.get("catatan", "").strip()
            upd = {"catatan": catatan}
            if can_transition(row["status"], new_status):
                upd["status"] = new_status
            sb.table("cuti").update(upd).eq("id", pengajuan_id).execute()
            data = sb.table("cuti").select("*").eq("id", pengajuan_id).execute().data
            row = data[0]
        allowed_targets = [s for s in STATUS_ORDER if can_transition(row["status"], s)]
        statuses = allowed_targets if row["status"] in allowed_targets else [row["status"]] + allowed_targets
        return render_template("detail.html", row=row,
                               jenis_labels=JENIS_LABEL, uptd_labels=UPTD_LABEL,
                               statuses=statuses)

    @app.route("/uploads/<path:filename>")
    @login_required
    def unduh_berkas(filename):
        data = get_client().storage.from_(config.STORAGE_BUCKET).download(filename)
        return send_file(io.BytesIO(data), as_attachment=True, download_name=filename,
                         mimetype=mimetypes.guess_type(filename)[0] or "application/octet-stream")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
