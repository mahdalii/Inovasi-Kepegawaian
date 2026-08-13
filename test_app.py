import sqlite3, tempfile, os, datetime, io
import config
from app import SCHEMA_SQL, init_db, create_app, gen_nomor, save_pengajuan, is_late, can_transition, validate_form

def test_init_db_membuat_tabel_cuti():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "test.db")
        init_db(db)
        conn = sqlite3.connect(db)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(cuti)")}
        conn.close()
    assert cols == {"id", "nomor", "nama", "nip", "jenis", "tgl_mulai",
                    "tgl_selesai", "berkas", "status", "catatan", "tgl_masuk"}

def test_is_late_hanya_status_baru_diproses():
    today = datetime.date(2026, 8, 13)
    assert is_late("Baru", "2026-08-10", today) is True
    assert is_late("Diproses", "2026-08-10", today) is True
    assert is_late("Disetujui", "2026-08-10", today) is False
    assert is_late("Ditolak", "2026-08-10", today) is False

def test_is_late_batas_tepat_2_hari():
    today = datetime.date(2026, 8, 13)
    assert is_late("Baru", "2026-08-11", today) is False

def test_update_status_menolak_mundur():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "test.db")
        init_db(db)
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        save_pengajuan(conn, "Budi", "123", "sakit", "2026-08-13",
                       "2026-08-14", "b.jpg", "2026-08-13")
        row = conn.execute("SELECT * FROM cuti LIMIT 1").fetchone()
        assert can_transition(row["status"], "Disetujui") is True
        assert can_transition("Disetujui", "Baru") is False
        conn.close()

def test_can_transition_hanya_maju():
    assert can_transition("Baru", "Diproses") is True
    assert can_transition("Diproses", "Disetujui") is True
    assert can_transition("Diproses", "Ditolak") is True
    assert can_transition("Disetujui", "Ditolak") is False
    assert can_transition("Ditolak", "Baru") is False

def test_validate_form_menolak_data_tidak_lengkap():
    errors = validate_form("", "123", "haha", "2026-08-13", "2026-08-14", False, True)
    assert any("nama" in e.lower() for e in errors)
    assert any("jenis" in e.lower() for e in errors)
    assert any("berkas" in e.lower() for e in errors)

def test_validate_form_menolak_tanggal_terbalik_dan_file_besar():
    errors = validate_form("A", "123", "tahunan", "2026-08-15", "2026-08-14", True, False)
    assert any("mulai" in e for e in errors)
    assert any("MB" in e for e in errors)

def test_gen_nomor_berurutan():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    assert gen_nomor(conn, datetime.date(2026, 8, 13)) == "CUT-2026-0001"
    conn.execute(
        "INSERT INTO cuti (nomor, nama, nip, jenis, tgl_mulai, tgl_selesai, berkas, status, catatan, tgl_masuk) "
        "VALUES ('CUT-2026-0001','X','1','sakit','2026-08-13','2026-08-14','b.jpg','Baru','','2026-08-13')"
    )
    conn.commit()
    assert gen_nomor(conn, datetime.date(2026, 8, 13)) == "CUT-2026-0002"
    conn.close()

def test_save_pengajuan_tersimpan_dan_status_baru():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "test.db")
        init_db(db)
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        nomor = save_pengajuan(conn, "Budi", "12345", "sakit",
                               "2026-08-13", "2026-08-14", "b.jpg", "2026-08-13")
        row = conn.execute("SELECT * FROM cuti WHERE nomor=?", (nomor,)).fetchone()
        conn.close()
        assert row["nama"] == "Budi"
        assert row["status"] == "Baru"


def _client_di_dir(d):
    config.DB_PATH = os.path.join(d, "test.db")
    config.UPLOAD_FOLDER = os.path.join(d, "uploads")
    app = create_app()
    return app.test_client()

def _post_berkas(client, nama_file, ukuran):
    return client.post("/", data={
        "nama": "Dewi", "nip": "99887", "jenis": "sakit",
        "tgl_mulai": "2026-08-13", "tgl_selesai": "2026-08-14",
        "berkas": (io.BytesIO(b"x" * ukuran), nama_file),
    }, content_type="multipart/form-data")

def test_upload_ditolak_bila_lebih_dari_5mb():
    with tempfile.TemporaryDirectory() as d:
        client = _client_di_dir(d)
        r = _post_berkas(client, "big.jpg", 5 * 1024 * 1024 + 1)
        assert r.status_code == 400
        assert "MB" in r.get_data(as_text=True)
        assert os.listdir(config.UPLOAD_FOLDER) == []
        conn = sqlite3.connect(config.DB_PATH)
        n = conn.execute("SELECT COUNT(*) FROM cuti").fetchone()[0]
        conn.close()
        assert n == 0

def test_upload_kecil_diterima_dan_tersimpan():
    with tempfile.TemporaryDirectory() as d:
        client = _client_di_dir(d)
        r = _post_berkas(client, "ok.jpg", 1024)
        assert r.status_code != 400
        assert len(os.listdir(config.UPLOAD_FOLDER)) == 1
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM cuti").fetchone()
        conn.close()
        assert row["nama"] == "Dewi"
        assert row["status"] == "Baru"
        assert row["nomor"].startswith("CUT-")

def test_catatan_tersimpan_tanpa_mengubah_status():
    with tempfile.TemporaryDirectory() as d:
        client = _client_di_dir(d)
        client.post("/login", data={"password": config.STAFF_PASSWORD})
        _post_berkas(client, "ok.jpg", 1024)
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM cuti").fetchone()
        pengajuan_id, status_awal = row["id"], row["status"]
        conn.close()
        r = client.post(f"/staff/{pengajuan_id}",
                        data={"status": status_awal, "catatan": "Perlu dokumen tambahan"})
        assert r.status_code == 200
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM cuti").fetchone()
        conn.close()
        assert row["status"] == status_awal
        assert row["catatan"] == "Perlu dokumen tambahan"

def test_status_terminal_tetap_ada_di_dropdown_detail():
    with tempfile.TemporaryDirectory() as d:
        client = _client_di_dir(d)
        client.post("/login", data={"password": config.STAFF_PASSWORD})
        _post_berkas(client, "ok.jpg", 1024)
        conn = sqlite3.connect(config.DB_PATH)
        conn.execute("UPDATE cuti SET status='Disetujui'")
        conn.commit()
        conn.close()
        r = client.get("/staff/1")
        assert "Disetujui" in r.get_data(as_text=True)
