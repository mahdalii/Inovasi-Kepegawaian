import sqlite3, tempfile, os, datetime
from app import SCHEMA_SQL, init_db, gen_nomor, save_pengajuan, is_late, can_transition, validate_form

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
