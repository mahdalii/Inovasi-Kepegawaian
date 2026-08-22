"""
Ponytail check: verify email notification triggers on submit + status change.
Run: python -m pytest test_email_notif.py -v 2>&1

Requires: pytest, flask, flask-mail
Does NOT require real SMTP: uses in-memory Flask-Mail (MAIL_SUPPRESS_SEND).
"""
import io
import pytest
from app import create_app, get_conn, config


@pytest.fixture
def client(monkeypatch, tmp_path):
    """App in test mode — email sending suppressed (captured, not sent)."""
    monkeypatch.setenv("MAIL_USERNAME", "test@example.com")
    monkeypatch.setenv("MAIL_PASSWORD", "fake-app-password")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    app = create_app()
    app.config["TESTING"] = True
    app.config["MAIL_SUPPRESS_SEND"] = True
    with app.test_client() as c:
        with app.app_context():
            yield c


def _submit(client, **data):
    defaults = {
        "nama": "Test User",
        "email": "test@example.com",
        "uptd": "batam_centre",
        "jenis": "tahunan",  # will be overridden
    }
    defaults.update(data)
    defaults["jenis"] = defaults.get("jenis", "tahunan")
    defaults.setdefault("tgl_mulai", "2026-08-25")
    defaults.setdefault("tgl_selesai", "2026-08-26")
    pdf = b"%PDF-1.4 test content"
    return client.post(
        "/",
        data={**defaults, "berkas": (io.BytesIO(pdf), "test.pdf")},
        content_type="multipart/form-data",
    )


def _login(client, password="admin123"):
    client.post("/login", data={"password": password})


def test_email_column_exists():
    """DB schema must have email column after migration."""
    import sqlite3
    conn = sqlite3.connect(config.DB_PATH)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(cuti)").fetchall()}
    conn.close()
    assert "email" in cols


def test_submit_triggers_email(client, monkeypatch):
    """Submitting form with valid email should attempt to send notification."""
    sent = []

    def fake_send(msg):
        sent.append({"recipients": msg.recipients, "subject": msg.subject})

    # Patch mail send to capture (since MAIL_SUPPRESS_SEND=True prevents real send)
    from app import mail
    monkeypatch.setattr(mail, "send", fake_send)

    r = _submit(client, jenis="tahunan", email="pegawai@example.com")
    assert r.status_code == 200
    assert "CUT-" in r.get_data(as_text=True)

    # email notification should be attempted
    assert len(sent) == 1
    assert sent[0]["recipients"] == ["pegawai@example.com"]
    assert "Pengajuan cuti diterima" in sent[0]["subject"]


def test_submit_invalid_email_rejected(client):
    """Invalid email format → 400 (email is required + validated)."""
    r = _submit(client, email="bukan-email", jenis="sakit")
    assert r.status_code == 400
    assert b"Email valid wajib diisi" in r.data


def test_status_change_triggers_email(client, monkeypatch):
    """Staff updating status should trigger email to requester."""
    sent = []

    def fake_send(msg):
        sent.append({"recipients": msg.recipients, "subject": msg.subject})

    from app import mail
    monkeypatch.setattr(mail, "send", fake_send)

    # Submit first
    _submit(client, email="requester@example.com", jenis="sakit")

    # Get the ID
    conn = get_conn()
    row = conn.execute("SELECT id FROM cuti WHERE email='requester@example.com' ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    assert row is not None
    pengajuan_id = row["id"]

    # Login + update status
    _login(client)
    r = client.post(f"/staff/{pengajuan_id}", data={"status": "Diproses", "catatan": "Proses verifikasi"})

    assert r.status_code == 200
    assert len(sent) == 2  # 1 from submit, 1 from status change
    # latest is the status change notif
    assert sent[-1]["recipients"] == ["requester@example.com"]
    assert "sedang diproses" in sent[-1]["subject"]


def test_no_notification_when_status_same(client, monkeypatch):
    """No email when user sets same status (no transition)."""
    sent = []

    def fake_send(msg):
        sent.append(msg)

    from app import mail
    monkeypatch.setattr(mail, "send", fake_send)

    _submit(client, email="same@example.com")
    conn = get_conn()
    row = conn.execute("SELECT id FROM cuti WHERE email='same@example.com' ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()

    _login(client)
    # Try to set same status (can_transition should block → no change → no email)
    client.post(f"/staff/{row['id']}", data={"status": "Baru", "catatan": "test"})

    # Only 1 email (from submit), not 2
    assert len(sent) == 1
