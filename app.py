import os
import sqlite3
import datetime
import uuid

from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, flash
import werkzeug

import config

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cuti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nomor TEXT NOT NULL UNIQUE,
    nama TEXT NOT NULL,
    nip TEXT NOT NULL,
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


def is_late(status, tgl_masuk, today=None):
    if status not in {"Baru", "Diproses"}:
        return False
    tgl = datetime.date.fromisoformat(tgl_masuk)
    today = today or datetime.date.today()
    return (today - tgl).days > 2


STATUS_ORDER = {"Baru": 1, "Diproses": 2, "Disetujui": 3, "Ditolak": 3}


def can_transition(current, new):
    return STATUS_ORDER.get(new, 0) > STATUS_ORDER.get(current, 99)


def validate_form(nama, nip, jenis, tgl_mulai, tgl_selesai, berkas_ok, file_size_ok):
    errors = []
    if not nama.strip():
        errors.append("Nama wajib diisi")
    if not nip.strip():
        errors.append("NIP wajib diisi")
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


def gen_nomor(conn, today=None):
    today = today or datetime.date.today()
    year = today.strftime("%Y")
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM cuti WHERE nomor LIKE ?", (f"CUT-{year}-%",)
    ).fetchone()
    return f"CUT-{year}-{row['n'] + 1:04d}"


def save_pengajuan(conn, nama, nip, jenis, tgl_mulai, tgl_selesai, berkas, tgl_masuk):
    nomor = gen_nomor(conn, datetime.date.fromisoformat(tgl_masuk))
    conn.execute(
        "INSERT INTO cuti (nomor, nama, nip, jenis, tgl_mulai, tgl_selesai, berkas, status, catatan, tgl_masuk) "
        "VALUES (?,?,?,?,?,?,?,'Baru','',?)",
        (nomor, nama.strip(), nip.strip(), jenis, tgl_mulai, tgl_selesai, berkas, tgl_masuk),
    )
    conn.commit()
    return nomor


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))
    app.config["UPLOAD_FOLDER"] = config.UPLOAD_FOLDER
    init_db()
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

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
                request.form.get("nama", ""), request.form.get("nip", ""),
                request.form.get("jenis", ""), request.form.get("tgl_mulai", ""),
                request.form.get("tgl_selesai", ""), berkas_ok, size_ok,
            )
            if errors:
                return render_template("form.html", errors=errors,
                                       jenis_labels=JENIS_LABEL,
                                       berkas_labels=BERKAS_LABEL,
                                       data=request.form), 400
            filename = safe_filename(f.filename)
            f.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            conn = get_conn()
            nomor = save_pengajuan(conn, request.form["nama"], request.form["nip"],
                                   request.form["jenis"], request.form["tgl_mulai"],
                                   request.form["tgl_selesai"], filename,
                                   datetime.date.today().isoformat())
            conn.close()
            return render_template("form.html", success=nomor,
                                   jenis_labels=JENIS_LABEL, berkas_labels=BERKAS_LABEL)
        return render_template("form.html", jenis_labels=JENIS_LABEL,
                               berkas_labels=BERKAS_LABEL)

    @app.route("/status", methods=["GET", "POST"])
    def status():
        rows, nip = [], request.form.get("nip", "")
        if request.method == "POST":
            conn = get_conn()
            rows = conn.execute(
                "SELECT * FROM cuti WHERE nip=? ORDER BY tgl_masuk DESC, id DESC",
                (nip.strip(),),
            ).fetchall()
            conn.close()
        return render_template("status.html", rows=rows, nip=nip,
                               jenis_labels=JENIS_LABEL)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000)