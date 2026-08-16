import datetime
from app import format_nomor, is_late, can_transition, validate_form, VALID_UPTD


def test_format_nomor():
    assert format_nomor("2026", 1) == "CUT-2026-0001"
    assert format_nomor("2026", 12) == "CUT-2026-0012"


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
    assert can_transition("Disetujui", "Baru") is False


def test_validate_form_lengkap_benar():
    errors = validate_form("Budi", "batam_centre", "sakit",
                           "2026-08-16", "2026-08-17", True, True)
    assert errors == []


def test_validate_form_menolak_input_buruk():
    assert "Nama wajib diisi" in validate_form("", "batam_centre", "sakit",
                                               "2026-08-16", "2026-08-17", True, True)
    assert "Tempat kerja tidak valid" in validate_form("Budi", "bogus", "sakit",
                                                       "2026-08-16", "2026-08-17", True, True)
    assert "Jenis cuti tidak valid" in validate_form("Budi", "batam_centre", "liburan",
                                                     "2026-08-16", "2026-08-17", True, True)
    assert "Berkas wajib diupload (PDF/JPG/PNG)" in validate_form(
        "Budi", "batam_centre", "sakit", "2026-08-16", "2026-08-17", False, True)
    assert "Ukuran berkas melebihi 4 MB" in validate_form(
        "Budi", "batam_centre", "sakit", "2026-08-16", "2026-08-17", True, False)