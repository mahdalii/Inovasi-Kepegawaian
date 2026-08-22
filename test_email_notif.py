"""
Ponytail check: verify email notification triggers + validation logic.
Run: python -m pytest test_email_notif.py -v

Tests NOT need real Supabase — mock email send + validate pure logic.
"""
import pytest
from unittest.mock import patch, MagicMock
from app import create_app, validate_form, send_cuti_notification, STATUS_ORDER, JENIS_LABEL, UPTD_LABEL


@pytest.fixture
def app_ctx():
    app = create_app()
    with app.app_context():
        yield app


class TestValidateForm:
    def test_valid_with_email(self):
        errors = validate_form("Siti", "siti@example.com", "batam_centre", "tahunan",
                               "2026-08-25", "2026-08-26", True, True)
        assert errors == []

    def test_missing_email_rejected(self):
        errors = validate_form("Siti", "", "batam_centre", "tahunan",
                               "2026-08-25", "2026-08-26", True, True)
        assert "Email valid wajib diisi" in errors

    def test_invalid_email_rejected(self):
        errors = validate_form("Siti", "bukan-email", "batam_centre", "sakit",
                               "2026-08-25", "2026-08-26", True, True)
        assert "Email valid wajib diisi" in errors

    def test_valid_email_variants(self):
        for e in ["a@b.co", "nama.desa@email.co.id", "user+tag@example.com"]:
            errors = validate_form("OK", e, "batam_centre", "alasan_penting",
                                   "2026-08-25", "2026-08-26", True, True)
            assert errors == [], f"Failed for {e}"


class TestSendCutiNotification:
    """Test send_cuti_notification: only sends when email present, errors are trapped."""
    def test_no_email_skips(self):
        row = {"email": None, "nama": "X", "nomor": "C-1", "status": "Baru",
               "jenis": "tahunan", "tgl_mulai": "2026-08-25", "tgl_selesai": "2026-08-26",
               "uptd": "batam_centre", "catatan": ""}
        with patch("app.mail") as mock_mail:
            send_cuti_notification(row)
            mock_mail.send.assert_not_called()  # no email to send

    def _row(self, status="Baru", email="pegawai@example.com", catatan=""):
        return {"email": email, "nama": "Andi", "nomor": "CUT-2026-001",
                "status": status, "jenis": "sakit", "tgl_mulai": "2026-08-25",
                "tgl_selesai": "2026-08-26", "uptd": "batam_centre", "catatan": catatan}

    def test_valid_email_sends_message(self, app_ctx):
        row = self._row(status="Disetujui", catatan="Disetujui atasan")
        with patch("app.mail") as mock_mail:
            send_cuti_notification(row)
            mock_mail.send.assert_called_once()
            msg = mock_mail.send.call_args[0][0]
            assert "disetujui" in msg.subject.lower()
            assert msg.recipients == ["pegawai@example.com"]

    def test_mail_error_never_crashes(self, app_ctx):
        """SMTP error must be trapped (no exception propagates)."""
        row = self._row(status="Ditolak")
        with patch("app.mail") as mock_mail:
            mock_mail.send.side_effect = Exception("SMTP down")
            # Should NOT raise
            send_cuti_notification(row)
            mock_mail.send.assert_called_once()

    def test_subject_map(self, app_ctx):
        subjects = {"Baru": "Pengajuan cuti diterima",
                    "Diproses": "Pengajuan cuti sedang diproses",
                    "Disetujui": "Pengajuan cuti disetujui",
                    "Ditolak": "Pengajuan cuti ditolak"}
        for status, expected_subj in subjects.items():
            row = self._row(status=status)
            with patch("app.mail") as m:
                send_cuti_notification(row)
                assert m.send.call_args[0][0].subject == expected_subj
