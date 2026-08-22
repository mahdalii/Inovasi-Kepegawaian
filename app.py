import os
import sqlite3
import datetime
import uuid

from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, flash
from flask_mail import Mail, Message
from dotenv import load_dotenv

load_dotenv()

import config

mail = Mail()

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cuti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nomor TEXT NOT NULL UNIQUE,
    nama TEXT NOT NULL,
    email TEXT,
    uptd TEXT NOT NULL,
    jenis TEXT NOT NULL,
    tgl_mulai TEXT NOT NULL,
    tgl_selesai TEXT NOT NULL,
    berkas TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Baru',
    catatan TEXT DEFAULT '',
    tgl_masuk TEXT NOT NULL
);
"""

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


def validate_form(nama, email, uptd, jenis, tgl_mulai, tgl_selesai, berkas_ok, file_size_ok):
    import re
    EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    errors = []
    if not nama.strip():
        errors.append("Nama wajib diisi")
    if not email or not EMAIL_RE.match(email.strip()):
        errors.append("Email valid wajib diisi")
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


def get_conn(db_path=None):
    conn = sqlite3.connect(db_path or config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path=None):
    conn = get_conn(db_path)
    conn.executescript(SCHEMA_SQL)
    # Migration: add 'email' column to existing tables
    cols = [r[1] for r in conn.execute("PRAGMA table_info(cuti)").fetchall()]
    if "email" not in cols:
        conn.execute("ALTER TABLE cuti ADD COLUMN email TEXT")
        conn.commit()
    conn.close()


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


# ---------- Email notification helpers ----------

def send_cuti_notification(row):
    """Kirim email notifikasi ke pegawai (row['email']) tentang status cuti.
    Tidak menghentikan request bila email gagal — error ditangkap & log."""
    import traceback

    # Only if at least one recipient
    if not row["email"]:
        return
    recipients = [row["email"]]

    subject_map = {
        "Baru": "Pengajuan cuti diterima",
        "Diproses": "Pengajuan cuti sedang diproses",
        "Disetujui": "Pengajuan cuti disetujui",
        "Ditolak": "Pengajuan cuti ditolak",
    }
    status_label = subject_map.get(row["status"], f"Update status: {row['status']}")
    jenis_label = JENIS_LABEL.get(row["jenis"], row["jenis"])

    body_lines = [
        f"Yth. {row['nama']},",
        "",
        status_label + ".",
        "",
        "Detail pengajuan:",
        f"  Nomor      : {row['nomor']}",
        f"  Jenis cuti : {jenis_label}",
        f"  Tanggal    : {row['tgl_mulai']} s/d {row['tgl_selesai']}",
        f"  UPTD       : {UPTD_LABEL.get(row['uptd'], row['uptd'])}",
        f"  Status     : {row['status']}",
    ]
    if row["catatan"]:
        body_lines += ["", f"Catatan: {row['catatan']}"]
    # Build status link — work inside/outside request context
    try:
        from flask import has_request_context
        if has_request_context():
            status_url = request.host_url.rstrip("/") + url_for("status")
        else:
            status_url = "[buka aplikasi untuk cek status]"
    except Exception:
        status_url = "[buka aplikASI untuk cek status]"

    body_lines += [
        "",
        "Cek status lengkap di: " + status_url,
        "",
        "Hormat kami,",
        "Sistem Cuti",
    ]

    msg = Message(
        subject=status_label,
        sender=config.MAIL_USERNAME,
        recipients=recipients,
        body="\n".join(body_lines),
    )
    try:
        mail.send(msg)
    except Exception:
        traceback.print_exc()


def gen_nomor(conn, today=None):
    today = today or datetime.date.today()
    year = today.strftime("%Y")
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM cuti WHERE nomor LIKE ?", (f"CUT-{year}-%",)
    ).fetchone()
    return f"CUT-{year}-{row['n'] + 1:04d}"


def save_pengajuan(conn, nama, email, uptd, jenis, tgl_mulai, tgl_selesai, berkas, tgl_masuk, berkas_path=None):
    last_error = None
    for _ in range(3):
        nomor = gen_nomor(conn, datetime.date.fromisoformat(tgl_masuk))
        try:
            conn.execute(
                "INSERT INTO cuti (nomor, nama, email, uptd, jenis, tgl_mulai, tgl_selesai, berkas, status, catatan, tgl_masuk) "
                "VALUES (?,?,?,?,?,?,?,?,?,'',?)",
                (nomor, nama.strip(), email.strip()[:255], uptd.strip(), jenis, tgl_mulai, tgl_selesai, berkas, 'Baru', tgl_masuk),
            )
            conn.commit()
            return nomor
        except sqlite3.IntegrityError as e:
            conn.rollback()
            last_error = e
    if berkas_path:
        os.remove(berkas_path)
    raise last_error


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["UPLOAD_FOLDER"] = config.UPLOAD_FOLDER
    init_db()
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

    # --- Mail configuration ---
    app.config["MAIL_SERVER"] = config.MAIL_SERVER
    app.config["MAIL_PORT"] = config.MAIL_PORT
    app.config["MAIL_USERNAME"] = config.MAIL_USERNAME
    app.config["MAIL_PASSWORD"] = config.MAIL_PASSWORD
    app.config["MAIL_USE_TLS"] = config.MAIL_USE_TLS
    mail.init_app(app)

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
                request.form.get("nama", ""), request.form.get("email", ""),
                request.form.get("uptd", ""), request.form.get("jenis", ""),
                request.form.get("tgl_mulai", ""), request.form.get("tgl_selesai", ""),
                berkas_ok, size_ok,
            )
            if errors:
                return render_template("form.html", errors=errors,
                                       jenis_labels=JENIS_LABEL,
                                       berkas_labels=BERKAS_LABEL,
                                       uptd_labels=UPTD_LABEL,
                                       data=request.form), 400
            filename = safe_filename(f.filename)
            berkas_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            f.save(berkas_path)
            conn = get_conn()
            nomor = save_pengajuan(conn, request.form["nama"], request.form.get("email", "").strip(),
                                   request.form["uptd"], request.form["jenis"],
                                   request.form["tgl_mulai"], request.form["tgl_selesai"], filename,
                                   datetime.date.today().isoformat(),
                                   berkas_path=berkas_path)
            # Fetch the saved row to send notification
            row = conn.execute("SELECT * FROM cuti WHERE nomor=?", (nomor,)).fetchone()
            conn.close()
            send_cuti_notification(row)  # fire-and-forget: errors logged inside helper
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
            conn = get_conn()
            rows = conn.execute(
                "SELECT * FROM cuti WHERE nomor LIKE ? OR nama LIKE ? "
                "ORDER BY tgl_masuk DESC, id DESC",
                (f"%{q}%", f"%{q}%"),
            ).fetchall()
            conn.close()
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
        conn = get_conn()
        q = request.args.get("q", "").strip()
        fstatus = request.args.get("status", "").strip()
        f_uptd = request.args.get("uptd", "").strip()
        sql = "SELECT * FROM cuti WHERE 1=1"
        params = []
        if q:
            sql += " AND (nama LIKE ? OR nomor LIKE ?)"
            params += [f"%{q}%"] * 2
        if fstatus:
            sql += " AND status=?"
            params.append(fstatus)
        if f_uptd:
            sql += " AND uptd=?"
            params.append(f_uptd)
        sql += " ORDER BY tgl_masuk DESC, id DESC"
        rows = conn.execute(sql, params).fetchall()
        conn.close()
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
        conn = get_conn()
        row = conn.execute("SELECT * FROM cuti WHERE id=?", (pengajuan_id,)).fetchone()
        if row is None:
            conn.close()
            return redirect(url_for("dashboard"))
        status_changed = False
        if request.method == "POST":
            new_status = request.form.get("status", "")
            catatan = request.form.get("catatan", "").strip()
            conn.execute("UPDATE cuti SET catatan=? WHERE id=?", (catatan, pengajuan_id))
            if can_transition(row["status"], new_status):
                conn.execute("UPDATE cuti SET status=? WHERE id=?", (new_status, pengajuan_id))
                status_changed = row["status"] != new_status
            conn.commit()
            row = conn.execute("SELECT * FROM cuti WHERE id=?", (pengajuan_id,)).fetchone()
        conn.close()
        # Send email notification when status changes
        if status_changed:
            send_cuti_notification(row)  # fire-and-forget: errors logged inside helper
        allowed_targets = [s for s in STATUS_ORDER if can_transition(row["status"], s)]
        statuses = allowed_targets if row["status"] in allowed_targets else [row["status"]] + allowed_targets
        return render_template("detail.html", row=row,
                               jenis_labels=JENIS_LABEL, uptd_labels=UPTD_LABEL,
                               statuses=statuses)

    @app.route("/uploads/<path:filename>")
    @login_required
    def unduh_berkas(filename):
        return send_from_directory(config.UPLOAD_FOLDER, filename)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)