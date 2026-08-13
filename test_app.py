import sqlite3, tempfile, os
from app import SCHEMA_SQL, init_db

def test_init_db_membuat_tabel_cuti():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "test.db")
        init_db(db)
        conn = sqlite3.connect(db)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(cuti)")}
        conn.close()
    assert cols == {"id", "nomor", "nama", "nip", "jenis", "tgl_mulai",
                    "tgl_selesai", "berkas", "status", "catatan", "tgl_masuk"}
