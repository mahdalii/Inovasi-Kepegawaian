import os
import sqlite3

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


def get_conn(db_path=None):
    conn = sqlite3.connect(db_path or config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path=None):
    conn = get_conn(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()