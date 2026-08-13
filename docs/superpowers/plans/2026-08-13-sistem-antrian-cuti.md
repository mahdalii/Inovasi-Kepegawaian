# Sistem Antrian Cuti — Implementation Plan

> **Untuk pekerja agentik:** WAJIB sub-skill: superpowers:subagent-driven-development (disarankan) atau superpowers:executing-plans untuk mengimplementasikan plan ini task-per-task. Langkah memakai checkbox (`- [ ]`) untuk pelacakan.

**Goal:** Aplikasi web kecil (Flask + SQLite) untuk antrian pengajuan cuti pegawai sehingga tidak ada pengajuan yang tenggelam.

**Architecture:** Satu aplikasi Flask di satu komputer kantor. Pegawai mengisi form via browser (LAN), data masuk SQLite, staff melihat dashboard antrian dengan penanda keterlambatan otomatis (> 2 hari, status masih Baru/Diproses → sorot merah + pulse). 4 halaman: form, cek status, dashboard, detail.

**Tech Stack:** Python 3.12, Flask 3.x, SQLite (modul stdlib `sqlite3`), pytest, HTML + CSS murni (tanpa JS framework), animasi CSS.

## Global Constraints

- Semua label antarmuka dalam Bahasa Indonesia.
- Status hanya: `Baru`, `Diproses`, `Disetujui`, `Ditolak` — hanya bisa maju (Baru→Diproses→Disetujui/Ditolak).
- Jenis cuti: `tahunan`, `sakit`, `alasan_penting` — tampil sebagai "Cuti Tahunan", "Cuti Sakit", "Cuti Alasan Penting".
- Keterlambatan: (hari ini − tanggal_masuk).days > 2 DAN status ∈ {Baru, Diproses}.
- Upload: hanya PDF/JPG/PNG, maks 5 MB, disimpan di `uploads/` dengan nama aman.
- Panel staff dilindungi kata sandi tunggal (env `STAFF_PASSWORD`, default `admin123` — ganti sebelum dipakai).
- Backup = salin file `cuti.db` dan folder `uploads/`.
- Uji: pytest untuk logika murni (bukan render HTML).

---

### Task 1: Scaffold proyek, konfigurasi, inisialisasi database

**Files:**
- Create: `requirements.txt`
- Create: `config.py`
- Create: `app.py`
- Create: `templates/` (folder)
- Create: `static/` (folder)
- Create: `uploads/` (folder)
- Create: `.gitignore`
- Test: `test_app.py`

**Interfaces:**
- Consumes: —
- Produces: `config.STAFF_PASSWORD`, `SCHEMA_SQL` (string DDL), fungsi `init_db(db_path)` yang membuat tabel `cuti` (kolom: `id`, `nomor`, `nama`, `nip`, `jenis`, `tgl_mulai`, `tgl_selesai`, `berkas`, `status`, `catatan`, `tgl_masuk`).

- [ ] **Step 1: Buat file dependensi & konfigurasi**

`requirements.txt`:
```
flask==3.0.3
pytest==8.3.2
```

`config.py`:
```python
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "cuti.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
MAX_UPLOAD_MB = 5
STAFF_PASSWORD = os.environ.get("STAFF_PASSWORD", "admin123")
```

- [ ] **Step 2: Tulis test yang gagal dulu (tabel & kolom)**

`test_app.py`:
```python
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
```

- [ ] **Step 3: Jalankan test, pastikan GAGAL**

Run: `pytest test_app.py::test_init_db_membuat_tabel_cuti -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 4: Implementasi minimal**

`app.py`:
```python
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
```

- [ ] **Step 5: Jalankan test, pastikan LULUS**

Run: `pytest test_app.py::test_init_db_membuat_tabel_cuti -v`
Expected: PASS

- [ ] **Step 6: `.gitignore`**

```
__pycache__/
*.pyc
cuti.db
uploads/*
!uploads/.gitkeep
.venv/
```

- [ ] **Step 7: Buat folder kosong + commit**

```bash
New-Item -ItemType Directory -Path templates, static, uploads -Force
git add requirements.txt config.py app.py test_app.py .gitignore
git commit -m "feat: scaffold flask app + database schema"
```

---

### Task 2: Logika murni — keterlambatan, transisi status, validasi

**Files:**
- Modify: `app.py`
- Modify: `test_app.py`

**Interfaces:**
- Consumes: —
- Produces:
  - `is_late(status: str, tgl_masuk: str, today: datetime.date) -> bool`
  - `can_transition(current: str, new: str) -> bool`
  - `VALID_JENIS = {"tahunan", "sakit", "alasan_penting"}`
  - `validate_form(nama, nip, jenis, tgl_mulai, tgl_selesai, berkas_ok, file_size_ok) -> list[str]` (daftar pesan error, kosong = valid)

- [ ] **Step 1: Tulis test yang gagal**

Tambahkan ke `test_app.py`:
```python
import datetime
from app import is_late, can_transition, validate_form

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
    errors = validate_form("", "123", "haha", "2026-08-13", "2026-08-14", True, True)
    assert any("nama" in e.lower() for e in errors)
    assert any("jenis" in e.lower() for e in errors)
    assert any("berkas" in e.lower() for e in errors)

def test_validate_form_menolak_tanggal_terbalik_dan_file_besar():
    errors = validate_form("A", "123", "tahunan", "2026-08-15", "2026-08-14", True, False)
    assert any("mulai" in e for e in errors)
    assert any("MB" in e for e in errors)
```

- [ ] **Step 2: Jalankan, pastikan GAGAL**

Run: `pytest test_app.py -v`
Expected: FAIL — `ImportError: cannot import name 'is_late'`

- [ ] **Step 3: Implementasi**

Tambahkan ke `app.py`:
```python
import datetime

VALID_JENIS = {"tahunan", "sakit", "alasan_penting"}


def is_late(status, tgl_masuk, today=None):
    if status not in {"Baru", "Diproses"}:
        return False
    tgl = datetime.date.fromisoformat(tgl_masuk)
    today = today or datetime.date.today()
    return (today - tgl).days > 2


STATUS_ORDER = {"Baru": 1, "Diproses": 2, "Disetujui": 3, "Ditolak": 3}


def can_transition(current, new):
    return STATUS_ORDER.get(new, 0) >= STATUS_ORDER.get(current, 99)


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
```

- [ ] **Step 4: Jalankan, pastikan LULUS**

Run: `pytest test_app.py -v`
Expected: PASS (semua 5 test)

- [ ] **Step 5: Commit**

```bash
git add app.py test_app.py
git commit -m "feat: core logic - late flag, status transition, form validation"
```

---

### Task 3: Form pegawai + penyimpanan + nomor pengajuan

**Files:**
- Modify: `app.py`
- Create: `templates/base.html`
- Create: `templates/form.html`
- Modify: `test_app.py`

**Interfaces:**
- Consumes: `get_conn`, `init_db`, `validate_form`, `config.UPLOAD_FOLDER`, `config.ALLOWED_EXTENSIONS`, `config.MAX_UPLOAD_MB`
- Produces:
  - `safe_filename(original: str) -> str`
  - `gen_nomor(conn, today: datetime.date) -> str` (format `CUT-YYYY-0001`)
  - `save_pengajuan(nama, nip, jenis, tgl_mulai, tgl_selesai, berkas, today_str) -> str` (kembali nomor)
  - `create_app() -> Flask` — aplikasi dengan semua rute (Task 3–6 menambah rute; lengkap di Task 6)

- [ ] **Step 1: Tulis test yang gagal**

Tambahkan ke `test_app.py`:
```python
import tempfile, os, datetime
from app import gen_nomor, save_pengajuan, init_db

def test_gen_nomor_berurutan():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)
    assert gen_nomor(conn, datetime.date(2026, 8, 13)) == "CUT-2026-0001"
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
```

- [ ] **Step 2: Jalankan, pastikan GAGAL**

Run: `pytest test_app.py::test_gen_nomor_berurutan test_app.py::test_save_pengajuan_tersimpan_dan_status_baru -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implementasi**

Tambahkan ke `app.py`:
```python
import uuid

from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, flash
import werkzeug

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
            size_ok = f is not None and f.content_length is not None and f.content_length <= config.MAX_UPLOAD_MB * 1024 * 1024
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

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000)
```

- [ ] **Step 4: Jalankan, pastikan LULUS**

Run: `pytest test_app.py -v`
Expected: PASS

- [ ] **Step 5: Buat template dasar + halaman form**

`templates/base.html`:
```html
<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block title %}Sistem Cuti{% endblock %} — Kepegawaian</title>
<link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
<header class="topbar"><h1>📋 Sistem Pengajuan Cuti</h1></header>
<main class="container">
{% block content %}{% endblock %}
</main>
<footer class="footer">Bagian Kepegawaian · Inovasi 2026</footer>
</body>
</html>
```

`templates/form.html`:
```html
{% extends "base.html" %}
{% block title %}Ajukan Cuti{% endblock %}
{% block content %}
{% if success %}
<div class="card animate-in">
  <h2>✅ Pengajuan berhasil dikirim</h2>
  <p>Simpan nomor pengajuan Anda:</p>
  <p class="nomor-besar">{{ success }}</p>
  <p>Gunakan nomor ini (atau NIP) untuk memantau status di halaman
     <a href="{{ url_for('status') }}">Cek Status</a>.</p>
  <a class="btn" href="{{ url_for('form_pegawai') }}">Ajukan cuti lagi</a>
</div>
{% else %}
<div class="card animate-in">
  <h2>Formulir Pengajuan Cuti</h2>
  {% if errors %}<ul class="errors">{% for e in errors %}<li>{{ e }}</li>{% endfor %}</ul>{% endif %}
  <form method="post" enctype="multipart/form-data">
    <label>Nama Lengkap <input name="nama" value="{{ data.nama if data }}" required></label>
    <label>NIP <input name="nip" value="{{ data.nip if data }}" required></label>
    <label>Jenis Cuti
      <select name="jenis" id="jenis" required>
        <option value="">— pilih jenis cuti —</option>
        {% for k, v in jenis_labels.items() %}
        <option value="{{ k }}">{{ v }}</option>
        {% endfor %}
      </select>
    </label>
    <label>Tanggal Mulai Cuti <input type="date" name="tgl_mulai" required></label>
    <label>Tanggal Selesai Cuti <input type="date" name="tgl_selesai" required></label>
    <label id="label-berkas">Berkas Pendukung <input type="file" name="berkas" accept=".pdf,.jpg,.jpeg,.png" required></label>
    <button class="btn btn-primary" type="submit">Kirim Pengajuan</button>
  </form>
  <p class="hint">Maks 5 MB · PDF / JPG / PNG</p>
</div>
{% endif %}
<script>
const labels = {
  tahunan: "Form persetujuan atasan (PDF/JPG/PNG)",
  sakit: "Bukti sakit (PDF/JPG/PNG)",
  alasan_penting: "Bukti alasan penting (PDF/JPG/PNG)"
};
document.getElementById("jenis").addEventListener("change", (e) => {
  document.querySelector("#label-berkas span").textContent = labels[e.target.value] || "Berkas Pendukung";
});
</script>
{% endblock %}
```

- [ ] **Step 6: Uji manual & commit**

```bash
python -m pip install -r requirements.txt
python app.py   # buka http://localhost:5000, submit form dengan file, cek nomor muncul
```

Expected: form tampil, submit dengan file valid → halaman sukses dengan nomor `CUT-2026-0001`.

```bash
git add app.py test_app.py templates/base.html templates/form.html
git commit -m "feat: employee cuti submission form with upload"
```

---

### Task 4: Halaman cek status pegawai (berdasarkan NIP)

**Files:**
- Modify: `app.py`
- Create: `templates/status.html`
- Create: `templates/_pengajuan_row.html` (parsial baris pengajuan, dipakai dashboard juga)

**Interfaces:**
- Consumes: `get_conn`
- Produces: rute `GET/POST /status` → `templates/status.html`; variabel konteks: `rows` (list sqlite3.Row), `nip`, `jenis_labels`, `status_badge(row)`.

- [ ] **Step 1: Implementasi rute**

`app.py` (dalam `create_app`, sebelum `return app`):
```python
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
```

- [ ] **Step 2: Buat template parsial + halaman status**

`templates/_pengajuan_row.html`:
```html
<tr>
  <td>{{ row.nomor }}</td>
  <td>{{ row.nama }}</td>
  <td>{{ jenis_labels[row.jenis] }}</td>
  <td>{{ row.tgl_mulai }} s/d {{ row.tgl_selesai }}</td>
  <td><span class="badge badge-{{ row.status|lower }} status-badge" data-status="{{ row.status|lower }}">{{ row.status }}</span></td>
</tr>
```

`templates/status.html`:
```html
{% extends "base.html" %}
{% block title %}Cek Status Cuti{% endblock %}
{% block content %}
<div class="card animate-in">
  <h2>🔍 Cek Status Pengajuan Cuti</h2>
  <form method="post">
    <label>Masukkan NIP Anda
      <input name="nip" value="{{ nip }}" placeholder="cth: 198505152010011001" required>
    </label>
    <button class="btn btn-primary" type="submit">Cek Status</button>
  </form>
</div>
{% if rows %}
<div class="card animate-in delay-1">
  <h3>Riwayat Pengajuan ({{ rows|length }})</h3>
  <table class="table">
    <thead><tr>
      <th>Nomor</th><th>Nama</th><th>Jenis</th><th>Tanggal Cuti</th><th>Status</th>
    </tr></thead>
    <tbody>
      {% for row in rows %}{% include "_pengajuan_row.html" %}{% endfor %}
    </tbody>
  </table>
</div>
{% elif request.method == "POST" %}
<div class="card animate-in"><p>Belum ada pengajuan untuk NIP tersebut.</p></div>
{% endif %}
{% endblock %}
```

- [ ] **Step 3: Uji manual & commit**

```bash
python app.py  # kirim 1 pengajuan pakai NIP tertentu, lalu cek di /status dengan NIP sama
```
Expected: pengajuan muncul dengan status Baru.

```bash
git add app.py templates/status.html templates/_pengajuan_row.html
git commit -m "feat: employee status check page"
```

---

### Task 5: Login staff + dashboard antrian dengan penanda keterlambatan

**Files:**
- Modify: `app.py`
- Create: `templates/login.html`
- Create: `templates/dashboard.html`

**Interfaces:**
- Consumes: `is_late`, `can_transition`, `config.STAFF_PASSWORD`
- Produces: `login_required` (decorator), rute `GET/POST /login`, `GET /logout`, `GET /staff` (dashboard). Variabel konteks dashboard: `rows`, `late_ids` (set id yang terlambat), `q`, `filter_status`, `jenis_labels`.

- [ ] **Step 1: Implementasi auth + dashboard**

`app.py` (dalam `create_app`, sebelum `return app`):
```python
    from functools import wraps

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("staff"):
                return redirect(url_for("login"))
            return view(*args, **kwargs)
        return wrapped

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            if request.form.get("password") == config.STAFF_PASSWORD:
                session["staff"] = True
                return redirect(url_for("dashboard"))
            flash("Kata sandi salah", "error")
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.pop("staff", None)
        return redirect(url_for("login"))

    @app.route("/staff")
    @login_required
    def dashboard():
        conn = get_conn()
        q = request.args.get("q", "").strip()
        fstatus = request.args.get("status", "").strip()
        sql = "SELECT * FROM cuti WHERE 1=1"
        params = []
        if q:
            sql += " AND (nama LIKE ? OR nip LIKE ? OR nomor LIKE ?)"
            params += [f"%{q}%"] * 3
        if fstatus:
            sql += " AND status=?"
            params.append(fstatus)
        sql += " ORDER BY tgl_masuk DESC, id DESC"
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        today = datetime.date.today()
        late_ids = {r["id"] for r in rows if is_late(r["status"], r["tgl_masuk"], today)}
        return render_template("dashboard.html", rows=rows, late_ids=late_ids,
                               q=q, filter_status=fstatus,
                               jenis_labels=JENIS_LABEL,
                               statuses=["Baru", "Diproses", "Disetujui", "Ditolak"])
```

- [ ] **Step 2: Template login & dashboard**

`templates/login.html`:
```html
{% extends "base.html" %}
{% block title %}Login Staff{% endblock %}
{% block content %}
<div class="card narrow animate-in">
  <h2>🔐 Panel Kepegawaian</h2>
  {% with messages = get_flashed_messages(with_categories=true) %}
    {% for cat, msg in messages %}<p class="errors">{{ msg }}</p>{% endfor %}
  {% endwith %}
  <form method="post">
    <label>Kata Sandi <input type="password" name="password" required></label>
    <button class="btn btn-primary" type="submit">Masuk</button>
  </form>
</div>
{% endblock %}
```

`templates/dashboard.html`:
```html
{% extends "base.html" %}
{% block title %}Dashboard Cuti{% endblock %}
{% block content %}
<div class="card animate-in">
  <div class="row-between">
    <h2>📥 Antrian Pengajuan Cuti</h2>
    <a class="btn" href="{{ url_for('logout') }}">Keluar</a>
  </div>
  <form method="get">
    <input name="q" value="{{ q }}" placeholder="Cari nama / NIP / nomor...">
    <select name="status">
      <option value="">Semua status</option>
      {% for s in statuses %}
      <option value="{{ s }}" {% if filter_status == s %}selected{% endif %}>{{ s }}</option>
      {% endfor %}
    </select>
    <button class="btn" type="submit">Filter</button>
  </form>
</div>

{% set terlambat = rows | selectattr('id', 'in', late_ids) | list %}
{% if terlambat %}
<div class="card late-card animate-in delay-1">
  <h3>⚠️ Perlu Perhatian (belum selesai > 2 hari)</h3>
  <table class="table">
    <thead><tr><th>Nomor</th><th>Nama</th><th>NIP</th><th>Jenis</th><th>Masuk</th><th>Status</th></tr></thead>
    <tbody>
    {% for row in terlambat %}
      <tr class="late-pulse">
        <td><a href="{{ url_for('detail', pengajuan_id=row.id) }}">{{ row.nomor }}</a></td>
        <td>{{ row.nama }}</td><td>{{ row.nip }}</td>
        <td>{{ jenis_labels[row.jenis] }}</td><td>{{ row.tgl_masuk }}</td>
        <td>{{ row.status }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% endif %}

<div class="card animate-in delay-2">
  <h3>Semua Pengajuan ({{ rows|length }})</h3>
  <table class="table">
    <thead><tr>
      <th>Nomor</th><th>Nama</th><th>NIP</th><th>Jenis</th>
      <th>Tanggal Cuti</th><th>Masuk</th><th>Status</th>
    </tr></thead>
    <tbody>
      {% for row in rows %}
      <tr class="{% if row.id in late_ids %}row-late{% endif %}">
        <td><a href="{{ url_for('detail', pengajuan_id=row.id) }}">{{ row.nomor }}</a></td>
        <td>{{ row.nama }}</td><td>{{ row.nip }}</td>
        <td>{{ jenis_labels[row.jenis] }}</td>
        <td>{{ row.tgl_mulai }} s/d {{ row.tgl_selesai }}</td>
        <td>{{ row.tgl_masuk }}</td>
        <td><span class="badge badge-{{ row.status|lower }} status-badge" data-status="{{ row.status|lower }}">{{ row.status }}</span></td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% if not rows %}<p>Belum ada pengajuan.</p>{% endif %}
</div>
{% endblock %}
```

- [ ] **Step 3: Uji manual & commit**

```bash
python app.py  # /login dengan admin123, cek /staff: isi 1 pengajuan baru, status Baru → masuk "Semua Pengajuan"
```
Expected: login berhasil, pengajuan tampil, tidak ada yang disorot (baru masuk).

```bash
git add app.py templates/login.html templates/dashboard.html
git commit -m "feat: staff login and dashboard with late warning"
```

---

### Task 6: Halaman detail + ubah status/catatan + unduh berkas

**Files:**
- Modify: `app.py`
- Create: `templates/detail.html`
- Modify: `test_app.py`

**Interfaces:**
- Consumes: `can_transition`, `login_required`, `config.UPLOAD_FOLDER`
- Produces: rute `GET/POST /staff/<int:pengajuan_id>` (detail + update status), rute `GET /uploads/<path:filename>` (login staff). Variabel konteks detail: `row`, `jenis_labels`, `allowed_targets` (daftar status tujuan yang valid dari `can_transition`).

- [ ] **Step 1: Tulis test yang gagal (transisi di level database)**

Tambahkan ke `test_app.py`:
```python
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
```

- [ ] **Step 2: Jalankan, pastikan GAGAL**

Run: `pytest test_app.py::test_update_status_menolak_mundur -v`
Expected: FAIL — `save_pengajuan` belum ada di namespace test? Tidak — sudah ada dari Task 3. Pastikan FAIL karena `can_transition` belum diimpor di test.

```bash
pytest test_app.py -v
```
Expected: FAIL bila belum ada; jika sudah LULUS, lanjut (test ini memvalidasi perilaku yang sudah dipakai dashboard).

- [ ] **Step 3: Implementasi rute detail + unduh**

`app.py` (dalam `create_app`, sebelum `return app`):
```python
    @app.route("/staff/<int:pengajuan_id>", methods=["GET", "POST"])
    @login_required
    def detail(pengajuan_id):
        conn = get_conn()
        row = conn.execute("SELECT * FROM cuti WHERE id=?", (pengajuan_id,)).fetchone()
        if row is None:
            conn.close()
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            new_status = request.form.get("status", "")
            if can_transition(row["status"], new_status):
                catatan = request.form.get("catatan", "").strip()
                conn.execute("UPDATE cuti SET status=?, catatan=? WHERE id=?",
                             (new_status, catatan, pengajuan_id))
                conn.commit()
                row = conn.execute("SELECT * FROM cuti WHERE id=?", (pengajuan_id,)).fetchone()
        conn.close()
        allowed_targets = [s for s in STATUS_ORDER if can_transition(row["status"], s)]
        return render_template("detail.html", row=row,
                               jenis_labels=JENIS_LABEL,
                               statuses=allowed_targets)

    @app.route("/uploads/<path:filename>")
    @login_required
    def unduh_berkas(filename):
        return send_from_directory(config.UPLOAD_FOLDER, filename)
```

- [ ] **Step 4: Template detail**

`templates/detail.html`:
```html
{% extends "base.html" %}
{% block title %}Detail {{ row.nomor }}{% endblock %}
{% block content %}
<div class="card animate-in">
  <div class="row-between">
    <h2>{{ row.nomor }} — {{ row.nama }}</h2>
    <a class="btn" href="{{ url_for('dashboard') }}">← Kembali</a>
  </div>
  <table class="table table-detail">
    <tr><th>Nama</th><td>{{ row.nama }}</td></tr>
    <tr><th>NIP</th><td>{{ row.nip }}</td></tr>
    <tr><th>Jenis Cuti</th><td>{{ jenis_labels[row.jenis] }}</td></tr>
    <tr><th>Tanggal Cuti</th><td>{{ row.tgl_mulai }} s/d {{ row.tgl_selesai }}</td></tr>
    <tr><th>Tanggal Masuk</th><td>{{ row.tgl_masuk }}</td></tr>
    <tr><th>Status</th><td><span class="badge badge-{{ row.status|lower }} status-badge" data-status="{{ row.status|lower }}">{{ row.status }}</span></td></tr>
    <tr><th>Berkas</th><td><a class="btn" href="{{ url_for('unduh_berkas', filename=row.berkas) }}" target="_blank">⬇ Unduh Berkas</a></td></tr>
  </table>

  <form method="post" class="status-form">
    <label>Ubah Status
      <select name="status">
        {% for s in statuses %}
        <option value="{{ s }}" {% if s == row.status %}selected{% endif %}>{{ s }}</option>
        {% endfor %}
      </select>
    </label>
    <label>Catatan
      <textarea name="catatan" rows="3">{{ row.catatan }}</textarea>
    </label>
    <button class="btn btn-primary" type="submit">Simpan</button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 5: Jalankan semua test + uji manual + commit**

Run: `pytest test_app.py -v`
Expected: PASS semuanya.

```bash
python app.py  # buka pengajuan di /staff, ubah status ke Disetujui, pastikan opsi mundur tidak ada
```
Expected: status berubah, dropdown hanya menampilkan status yang valid.

```bash
git add app.py templates/detail.html test_app.py
git commit -m "feat: detail page with status update and file download"
```

---

### Task 7: Styling + animasi CSS + mode gelap

**Files:**
- Create: `static/style.css`

**Interfaces:**
- Consumes: kelas HTML yang dipakai template (`.card`, `.badge badge-*`, `.late-pulse`, `.row-late`, `.animate-in delay-*`, `.btn`, `.table`, `.errors`, `.nomor-besar`, `.topbar`, `.footer`, `.row-between`, `.narrow`, `.status-badge`)

- [ ] **Step 1: Tulis CSS lengkap**

`static/style.css`:
```css
:root {
  --bg: #f1f5f9; --card: #ffffff; --text: #1e293b; --muted: #64748b;
  --primary: #2563eb; --primary-dark: #1d4ed8; --border: #e2e8f0;
  --late: #fee2e2; --late-border: #f87171;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f172a; --card: #1e293b; --text: #e2e8f0; --muted: #94a3b8;
    --primary: #3b82f6; --primary-dark: #2563eb; --border: #334155;
    --late: #450a0a; --late-border: #ef4444;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; font-family: "Segoe UI", system-ui, sans-serif;
  background: var(--bg); color: var(--text); min-height: 100vh;
}
.topbar { background: linear-gradient(135deg, var(--primary), var(--primary-dark)); color: #fff; padding: 1rem 1.5rem; }
.topbar h1 { margin: 0; font-size: 1.25rem; }
.container { max-width: 1000px; margin: 1.5rem auto; padding: 0 1rem; }
.footer { text-align: center; color: var(--muted); padding: 1.5rem; font-size: .85rem; }
.card {
  background: var(--card); border: 1px solid var(--border); border-radius: 12px;
  padding: 1.25rem 1.5rem; margin-bottom: 1.25rem;
  box-shadow: 0 1px 3px rgba(0,0,0,.08);
}
.card.narrow { max-width: 420px; margin-left: auto; margin-right: auto; }
.row-between { display: flex; justify-content: space-between; align-items: center; gap: .5rem; flex-wrap: wrap; }
label { display: block; margin-bottom: .9rem; font-weight: 600; }
input, select, textarea {
  display: block; width: 100%; margin-top: .35rem; padding: .6rem .75rem;
  border: 1px solid var(--border); border-radius: 8px; font-size: 1rem;
  background: var(--card); color: var(--text);
}
.btn {
  display: inline-block; padding: .55rem 1.1rem; border-radius: 8px;
  border: 1px solid var(--border); background: var(--card); color: var(--text);
  text-decoration: none; font-weight: 600; cursor: pointer; font-size: .95rem;
  transition: transform .12s ease, box-shadow .12s ease;
}
.btn:active { transform: scale(.96); }
.btn-primary { background: var(--primary); border-color: var(--primary); color: #fff; }
.btn-primary:hover { background: var(--primary-dark); box-shadow: 0 4px 12px rgba(37,99,235,.35); }
.table { width: 100%; border-collapse: collapse; }
.table th, .table td { padding: .6rem .75rem; text-align: left; border-bottom: 1px solid var(--border); }
.table th { color: var(--muted); font-size: .8rem; text-transform: uppercase; letter-spacing: .03em; }
.table-detail th { width: 160px; }
.row-late { background: var(--late); }
.row-late td { border-color: var(--late-border); }
.badge { padding: .25rem .7rem; border-radius: 999px; font-size: .8rem; font-weight: 700; transition: color .3s, background .3s; }
.badge-baru { background: #dbeafe; color: #1e40af; }
.badge-diproses { background: #fef9c3; color: #854d0e; }
.badge-disetujui { background: #dcfce7; color: #166534; }
.badge-ditolak { background: #fee2e2; color: #991b1b; }
@media (prefers-color-scheme: dark) {
  .badge-baru { background: #1e3a8a; color: #bfdbfe; }
  .badge-diproses { background: #713f12; color: #fef08a; }
  .badge-disetujui { background: #14532d; color: #bbf7d0; }
  .badge-ditolak { background: #7f1d1d; color: #fecaca; }
}
.late-card { border-color: var(--late-border); }
@keyframes animateIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
.animate-in { animation: animateIn .45s ease both; }
.delay-1 { animation-delay: .15s; }
.delay-2 { animation-delay: .3s; }
@keyframes pulse { 0%,100% { box-shadow: 0 0 0 0 rgba(239,68,68,.5); } 50% { box-shadow: 0 0 0 8px rgba(239,68,68,0); } }
.late-pulse { animation: pulse 1.6s ease-in-out 3; }
.status-badge { display: inline-block; transition: transform .2s; }
.status-badge:hover { transform: scale(1.08); }
.errors { background: var(--late); border: 1px solid var(--late-border); border-radius: 8px; padding: .8rem 1rem 0.8rem 2rem; margin-bottom: 1rem; }
.nomor-besar { font-size: 1.6rem; font-weight: 800; color: var(--primary); }
.hint { color: var(--muted); font-size: .85rem; }
a { color: var(--primary); }
```

- [ ] **Step 2: Uji visual manual**

```bash
python app.py  # buka /, /status, /login, /staff; ubah lebar browser + mode gelap OS
```
Expected: animasi fade-in muncul, badge berwarna sesuai status, baris terlambat berdenyut, mode gelap aktif mengikuti OS.

- [ ] **Step 3: Commit**

```bash
git add static/style.css
git commit -m "feat: styling, animations, dark mode"
```

---

### Task 8: README panduan pemakaian + pengujian akhir

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: semua yang sudah ada

- [ ] **Step 1: Tulis README**

`README.md`:
```markdown
# Sistem Pengajuan Cuti (Inovasi Kepegawaian)

Aplikasi antrian pengajuan cuti pegawai agar tidak ada pengajuan yang tenggelam.

## Menjalankan

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Buka di komputer lain (LAN): `http://<IP-KOMPUTER>:5000`.
Cari IP: `ipconfig` → IPv4 Address.

## Kata Sandi Staff

Default: `admin123`. WAJIB diganti sebelum dipakai:

```
$env:STAFF_PASSWORD="sandi-anda"
python app.py
```

## Backup

Salin 2 hal: file `cuti.db` dan folder `uploads/`.

## Pengujian

```
pytest test_app.py -v
```

## Cara Pakai Ringkas

- Pegawai → halaman utama: isi form, dapat nomor `CUT-2026-XXXX`.
- Pegawai → "Cek Status": masukkan NIP.
- Staff → /login → dashboard: baris merah = pengajuan > 2 hari belum selesai.
- Staff → detail: unduh berkas, ubah status, tulis catatan.
```

- [ ] **Step 2: Jalankan seluruh pengujian akhir**

Run: `pytest test_app.py -v`
Expected: PASS semua.

- [ ] **Step 3: Uji alur end-to-end manual**

```bash
python app.py
```
1. Buka `/`, kirim pengajuan (pakai file kecil) → catat nomor.
2. Buka `/status`, cek dengan NIP → muncul.
3. `/login` admin123 → dashboard → pengajuan tampil.
4. Buka detail → unduh berkas → ubah status Disetujui → kembali → badge hijau.
5. (Opsional) ubah tanggal database `tgl_masuk` jadi 5 hari lalu → baris merah + denyut.

- [ ] **Step 4: Commit final**

```bash
git add README.md
git commit -m "docs: usage guide and final checks"
```

---

## Self-Review Notes

- Spec bagian 3 (4 halaman) → Task 3/4/5/6. Spec bagian 4 (logika) → Task 2.
- Spec bagian 8 (visual & animasi) → Task 7. Keamanan (kata sandi, upload) → Task 5/3.
- Status nilai konsisten di semua template: `badge-{{ row.status|lower }}` ↔ `baru/diproses/disetujui/ditolak` (Task 4/5/6/7).
- `can_transition` memakai `STATUS_ORDER` — Ditolak dan Disetujui same rank, tidak bisa mundur. Konsisten antar task.