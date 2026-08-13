import os
import sqlite3
import datetime

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