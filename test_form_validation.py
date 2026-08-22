"""
Ponytail check: verify form validation logic.
Run: python -m pytest test_form_validation.py -v
"""
import pytest
from app import validate_form


class TestValidateForm:
    def test_valid(self):
        errors = validate_form("Siti", "batam_centre", "tahunan",
                               "2026-08-25", "2026-08-26", True, True)
        assert errors == []

    def test_missing_nama_rejected(self):
        errors = validate_form("", "batam_centre", "tahunan",
                               "2026-08-25", "2026-08-26", True, True)
        assert "Nama wajib diisi" in errors

    def test_missing_uptd_rejected(self):
        errors = validate_form("Siti", "", "tahunan",
                               "2026-08-25", "2026-08-26", True, True)
        assert "Unit kerja wajib diisi" in errors

    def test_invalid_uptd_rejected(self):
        errors = validate_form("Siti", "mars", "tahunan",
                               "2026-08-25", "2026-08-26", True, True)
        assert "Unit kerja tidak valid" in errors

    def test_invalid_jenis_rejected(self):
        errors = validate_form("Siti", "batam_centre", "bukan_jenis",
                               "2026-08-25", "2026-08-26", True, True)
        assert "Jenis cuti tidak valid" in errors

    def test_tanggal_terbalik_rejected(self):
        errors = validate_form("Siti", "batam_centre", "tahunan",
                               "2026-08-26", "2026-08-25", True, True)
        assert any("tidak boleh lebih lama" in e for e in errors)

    def test_berkas_wajib(self):
        errors = validate_form("Siti", "batam_centre", "sakit",
                               "2026-08-25", "2026-08-26", False, True)
        assert any("Berkas wajib" in e for e in errors)

    def test_ukuran_maks(self):
        errors = validate_form("Siti", "batam_centre", "alasan_penting",
                               "2026-08-25", "2026-08-26", True, False)
        assert any("melebihi" in e for e in errors)
