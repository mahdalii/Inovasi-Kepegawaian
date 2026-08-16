# Deploy Online (Vercel + Supabase) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pindahkan Sistem Pengajuan Cuti dari SQLite lokal ke Vercel serverless + Supabase Postgres/Storage, supaya pegawai bisa isi form cuti dari mana saja lewat satu URL publik.

**Architecture:** Flask app (tidak berubah tampilan) dijalankan sebagai satu serverless function Vercel. SQLite diganti Supabase Postgres (tabel `cuti` + tabel `counter` untuk nomor urut). Upload berkas diganti Supabase Storage bucket privat `berkas`, semua baca lewat route `/uploads/` yang wajib login staff. Data lama TIDAK dipindah (mulai baru).

**Tech Stack:** Python 3.12, Flask 3.0.3 (sudah), `supabase>=2.5` (baru), Vercel (@vercel/python), Supabase project `lidxvlxfvtdhzaermgvi`.

## Global Constraints

- `MAX_UPLOAD_MB` dikurangi dari 5 → **4** (batas body Vercel hobby 4.5MB).
- Staff cuma satu akun (password env `STAFF_PASSWORD`, layak admin tunggal Mahdali).
- Tidak pakai RLS — service role key bypass RLS, key hanya di env server.
- Bucket storage `berkas` **privat**, tidak ada akses publik.
- `templates/*` tidak berubah (tampilan & semua label sama).
- Nama route, alur status, transisi status tidak berubah.
- Test: logika murni (is_late, can_transition, validate_form, format_nomor) offline; alur DB/storage diverifikasi manual via browser E2E.
- Supabase project: `lidxvlxfvtdhzaermgvi` (aktif, region ap-northeast-1).

---

### Task 1: Supabase — skema DB + bucket storage

**Files:** tidak ada (langsung ke Supabase project via MCP)

**Interfaces:**
- Produces: tabel `cuti` (kolom: id bigint identity PK, nomor text unique, nama, uptd, jenis, tgl_mulai, tgl_selesai, berkas, status default 'Baru', catatan default '', tgl_masuk), tabel `counter` (id int PK, tahun text, nilai int), bucket storage `berkas` (privat).

- [ ] **Step 1: Terapkan migrasi DDL**

Via `supabase apply_migration` (`project_id: lidxvlxfvtdhzaermgvi`, `name: add_cuti_counter`, query):

```sql
create table if not exists cuti (
  id bigint generated always as identity primary key,
  nomor text not null unique,
  nama text not null,
  uptd text not null,
  jenis text not null,
  tgl_mulai text not null,
  tgl_selesai text not null,
  berkas text not null,
  status text not null default 'Baru',
  catatan text not null default '',
  tgl_masuk text not null
);

create table if not exists counter (
  id integer primary key,
  tahun text not null,
  nilai integer not null
);
```

- [ ] **Step 2: Buat bucket storage `berkas` (privat)**

Via `supabase execute_sql`:

```sql
insert into storage.buckets (id, name, public)
values ('berkas', 'berkas', false)
on conflict (id) do nothing;
```

- [ ] **Step 3: Verifikasi**

Via `supabase list_tables` → pastikan `cuti` & `counter` ada di schema public.

Expected: dua tabel terdaftar.

- [ ] **Step 4: Commit** (tidak ada file berubah → tanpa commit)

---

### Task 2: `config.py` env var + `requirements.txt`

**Files:**
- Modify: `config.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `config.SUPABASE_URL`, `config.SUPABASE_SERVICE_ROLE_KEY`, `config.STORAGE_BUCKET = "berkas"`, `config.MAX_UPLOAD_MB = 4`. `config.ALLOWED_EXTENSIONS`, `config.STAFF_PASSWORD` tetap.
- Konsumsi: `app.py` Task 3.

- [ ] **Step 1: Tulis ulang `config.py`**

```python
import os

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
MAX_UPLOAD_MB = 4
STAFF_PASSWORD = os.environ.get("STAFF_PASSWORD", "admin123")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
STORAGE_BUCKET = "berkas"
```

(Hapus `BASE_DIR`, `DB_PATH`, `UPLOAD_FOLDER` — tidak dipakai lagi.)

- [ ] **Step 2: Tambah dependency `supabase` di `requirements.txt`**

```
flask==3.0.3
pytest==8.3.2
supabase>=2.5
```

- [ ] **Step 3: Install & validasi import**

Run (PowerShell):
```powershell
pip install -r requirements.txt
python -c "import supabase; print(supabase.__version__)"
```
Expected: versi tercetak, tidak ada error.

- [ ] **Step 4: Commit**

```bash
git add config.py requirements.txt
git commit -m "chore: pindah config ke Supabase env, max upload 4MB"
```

---

### Task 3: `app.py` — data layer Supabase + rewrites route

**Files:**
- Modify: `app.py` (tulis ulang)

**Interfaces:**
- Consumes: `config.SUPABASE_URL`, `config.SUPABASE_SERVICE_ROLE_KEY`, `config.STORAGE_BUCKET`, `config.MAX_UPLOAD_MB`, `config.STAFF_PASSWORD`.
- Produces (dipakai test Task 4 & E2E Task 7):
  - `format_nomor(tahun: str, nilai: int) -> str` → `"CUT-2026-0001"`
  - `get_client() -> supabase.Client` (lazy, cached global)
  - `get_nomor_value(sb, tahun: str) -> int` (increment counter, return nilai baru)
  - `save_pengajuan(sb, nama, uptd, jenis, tgl_mulai, tgl_selesai, filename, tgl_masuk) -> nomor`
  - `is_late`, `can_transition`, `validate_form`, `JENIS_LABEL`, `BERKAS_LABEL`, `UPTD_LABEL` — **tidak berubah**.
  - Keluar: `app = create_app()` (module-level, tetap di `app.py`) untuk Vercel.

- [ ] **Step 1: Impor & helper client**

Ganti blok import + hapus `import sqlite3` / `config.DB_PATH`. Tambah:

```python
import io
import mimetypes
from supabase import create_client
import config
```

Dan ganti helper DB:

```python
_client = None

def get_client():
    global _client
    if _client is None:
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY)
    return _client
```

Hapus `init_db`, `get_conn`, `SCHEMA_SQL`.

- [ ] **Step 2: Nomor urut lewat counter**

Hapus `gen_nomor` (versi sqlite). Tambah:

```python
def format_nomor(tahun, nilai):
    return f"CUT-{tahun}-{nilai:04d}"

def get_nomor_value(sb, tahun):
    row = sb.table("counter").select("*").eq("tahun", tahun).execute().data
    if row:
        nilai = row[0]["nilai"] + 1
        sb.table("counter").update({"nilai": nilai}).eq("tahun", tahun).execute()
    else:
        nilai = 1
        sb.table("counter").insert({"id": 1, "tahun": tahun, "nilai": nilai}).execute()
    return nilai
# ponytail: counter satu baris per tahun, lock lewat insert/update.
# Konkurensi tinggi bisa lompat nomor — upgrade ke sequence postgres kalau perlu.
```

- [ ] **Step 3: `save_pengajuan` di Postgres**

```python
def save_pengajuan(sb, nama, uptd, jenis, tgl_mulai, tgl_selesai, filename, tgl_masuk):
    tahun = tgl_masuk[:4]
    for _ in range(3):
        nilai = get_nomor_value(sb, tahun)
        nomor = format_nomor(tahun, nilai)
        try:
            sb.table("cuti").insert({
                "nomor": nomor, "nama": nama.strip(), "uptd": uptd.strip(),
                "jenis": jenis, "tgl_mulai": tgl_mulai, "tgl_selesai": tgl_selesai,
                "berkas": filename, "status": "Baru", "catatan": "", "tgl_masuk": tgl_masuk,
            }).execute()
            return nomor
        except Exception:
            continue
    raise RuntimeError("Gagal menyimpan pengajuan")
```

- [ ] **Step 4: Route `/` (form) — upload ke Storage + simpan**

Di `create_app`, hapus `init_db()` dan `os.makedirs(config.UPLOAD_FOLDER)`. Ganti `form_pegawai` POST path (setelah `errors` kosong & `f` valid):

```python
            data = f.read()
            filename = safe_filename(f.filename)
            try:
                get_client().storage.from_(config.STORAGE_BUCKET).upload(filename, data)
            except Exception:
                errors = ["Gagal mengunggah berkas. Coba file lebih kecil (maks 4MB) atau coba lagi."]
                return render_template("form.html", errors=errors,
                                       jenis_labels=JENIS_LABEL, berkas_labels=BERKAS_LABEL,
                                       uptd_labels=UPTD_LABEL, data=request.form), 400
            try:
                nomor = save_pengajuan(get_client(),
                                       request.form["nama"], request.form["uptd"],
                                       request.form["jenis"], request.form["tgl_mulai"],
                                       request.form["tgl_selesai"], filename,
                                       datetime.date.today().isoformat())
            except Exception:
                get_client().storage.from_(config.STORAGE_BUCKET).remove([filename])
                errors = ["Gagal menyimpan pengajuan. Silakan coba lagi."]
                return render_template("form.html", errors=errors,
                                       jenis_labels=JENIS_LABEL, berkas_labels=BERKAS_LABEL,
                                       uptd_labels=UPTD_LABEL, data=request.form), 500
            return render_template("form.html", success=nomor,
                                   jenis_labels=JENIS_LABEL, berkas_labels=BERKAS_LABEL,
                                   uptd_labels=UPTD_LABEL)
```

Bagian GET `/`, upload-size check (`size_ok` pakai `config.MAX_UPLOAD_MB`) tetap.

- [ ] **Step 5: Route `/status`**

Ganti blok query `sqlite`:

```python
            rows = get_client().table("cuti").select("*") \
                .or_(f"nomor.ilike.%{q}%,nama.ilike.%{q}%") \
                .order("tgl_masuk", desc=True).order("id", desc=True) \
                .execute().data
```

Sisanya (render) tetap.

- [ ] **Step 6: Route `/staff` (dashboard)**

Ganti query:

```python
        b = get_client().table("cuti").select("*")
        if q:
            b = b.or_(f"nomor.ilike.%{q}%,nama.ilike.%{q}%")
        if fstatus:
            b = b.eq("status", fstatus)
        if f_uptd:
            b = b.eq("uptd", f_uptd)
        b = b.order("tgl_masuk", desc=True).order("id", desc=True)
        rows = b.execute().data
```

`late_ids`, render tetap (rows berupa list-of-dict; akses `r["id"]`, `r["status"]`, `r["tgl_masuk"]` tetap bekerja).

- [ ] **Step 7: Route `/staff/<int:pengajuan_id>` (detail)**

Ganti fetch & update:

```python
        sb = get_client()
        data = sb.table("cuti").select("*").eq("id", pengajuan_id).execute().data
        if not data:
            return redirect(url_for("dashboard"))
        row = data[0]
        if request.method == "POST":
            new_status = request.form.get("status", "")
            catatan = request.form.get("catatan", "").strip()
            upd = {"catatan": catatan}
            if can_transition(row["status"], new_status):
                upd["status"] = new_status
            sb.table("cuti").update(upd).eq("id", pengajuan_id).execute()
            data = sb.table("cuti").select("*").eq("id", pengajuan_id).execute().data
            row = data[0]
```

Sisanya (allowed_targets, render) tetap.

- [ ] **Step 8: Route `/uploads/<path:filename>`**

```python
    @app.route("/uploads/<path:filename>")
    @login_required
    def unduh_berkas(filename):
        data = get_client().storage.from_(config.STORAGE_BUCKET).download(filename)
        return send_file(io.BytesIO(data), as_attachment=True, download_name=filename,
                         mimetype=mimetypes.guess_type(filename)[0] or "application/octet-stream")
```

Impor `send_file` dari flask di baris import.

- [ ] **Step 9: `create_app` bersih dari sqlite**

Pastikan tidak ada sisa `get_conn()`, `init_db`, `SCHEMA_SQL`, `UPLOAD_FOLDER`, `config.DB_PATH` di file. `if __name__ == "__main__": app.run(...)` boleh tetap (jalan lokal kalau env terisi).

- [ ] **Step 10: Boot check lokal**

Run (PowerShell, env harus terisi dulu — atau sengaja gagal):

```powershell
python -c "import app; print('ok', app.app is not None)"
```
Expected:
- Jika `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` kosong → `create_client` error saat FIRST request, tapi import tetap ok karena lazy → print `ok True`. Import TIDAK boleh crash.

- [ ] **Step 11: Commit**

```bash
git add app.py
git commit -m "feat: pindah data layer ke Supabase Postgres + Storage"
```

---

### Task 4: `test_app.py` — test logika murni offline

**Files:**
- Rewrite: `test_app.py`

**Interfaces:**
- Consumes: `format_nomor`, `is_late`, `can_transition`, `validate_form`, `VALID_UPTD` dari `app`.
- Produces: suite pytest yang lolos offline (tanpa Supabase).

- [ ] **Step 1: Tulis ulang `test_app.py`**

```python
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
```

(Catatan: string error ukuran menggunakan `config.MAX_UPLOAD_MB` = 4 di `app.py` — pastikan pesan error tetap tepat, lihat Task 3; `validate_form` membaca `file_size_ok` boolean, teks pesan di app.py harus menyebut "4 MB".)

- [ ] **Step 2: Perbaiki pesan error ukuran di `app.py`**

Di `validate_form` ganti `"Ukuran berkas melebihi 5 MB"` → `f"Ukuran berkas melebihi {config.MAX_UPLOAD_MB} MB"` (impor `config` sudah ada).

- [ ] **Step 3: Jalankan test — harus lolos offline**

Run (PowerShell):
```powershell
python -m pytest test_app.py -v
```
Expected: 6 test PASS, tanpa akses Supabase.

- [ ] **Step 4: Commit**

```bash
git add test_app.py app.py
git commit -m "test: adaptasi ke logika murni, drop test sqlite"
```

---

### Task 5: `vercel.json` + cek boot mesin lokal

**Files:**
- Create: `vercel.json`

**Interfaces:**
- Produces: konfigurasi build/rewrite Vercel untuk satu function Flask di `app.py:app`.

- [ ] **Step 1: Buat `vercel.json`**

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "builds": [
    { "src": "app.py", "use": "@vercel/python" }
  ],
  "rewrites": [
    { "source": "/(.*)", "destination": "/app" }
  ]
}
```

- [ ] **Step 2: Amankan file sensitif**

Pastikan `.gitignore` memuat `.venv/`, `__pycache__/`, `*.db`, `uploads/` (sudah ada sebelumnya — verifikasi). `templates/` dan `static/` TIDAK di-ignore.

- [ ] **Step 3: Commit**

```bash
git add vercel.json
git commit -m "chore: konfigurasi build Vercel untuk Flask"
```

---

### Task 6: Vercel — buat project, env var, deploy

**Files:** tidak ada di repo (operasi Vercel/MCP)

**Interfaces:**
- Produces: project Vercel `inovasikepegawaian` terhubung ke repo `mahdalii/Inovasi-Kepegawaian` (branch `main`), env var terisi, deployment production live.

- [ ] **Step 1: Dapatkan nilai env yang perlu diinput manual**

Via `supabase get_project_url` dapatkan `url`. **Service role key TIDAK tersedia lewat MCP** — minta user salin dari Supabase Dashboard → Settings → API → `service_role` key. Kirim ke user perintah bantuan:

> Ketik: `! <nilai>` di prompt untuk menjalankan langkah manual (lihat Step 3).

- [ ] **Step 2: Buat project Vercel dari repo**

Via `vercel create_git_project`:
- `repo: "mahdalii/Inovasi-Kepegawaian"`
- `teamId: "team_oSJ4ZKdbMShLxhQPAQ6S1ikt"`
- `projectName: "inovasikepegawaian"`

Expected: project ter-create, deployment preview otomatis (gagal karena env belum ada — wajar).

- [ ] **Step 3: Set env var production**

Butuh 4 nilai: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `STAFF_PASSWORD`, `SECRET_KEY`.

Generate password & secret:
```powershell
python -c "import secrets; print(secrets.token_urlsafe(24))"
```
Setiap var (untuk `SUPABASE_SERVICE_ROLE_KEY` & `STAFF_PASSWORD` isi manual/nilai pilihan user):
```powershell
"<NILAI>" | npx vercel env add SUPABASE_URL production
"<NILAI>" | npx vercel env add SUPABASE_SERVICE_ROLE_KEY production
"<NILAI>" | npx vercel env add STAFF_PASSWORD production
"<NILAI>" | npx vercel env add SECRET_KEY production
```
Fallback: dashboard Vercel → project → Settings → Environment Variables.

- [ ] **Step 4: Deploy production**

```powershell
npx vercel deploy --prod --yes
```
Expected: selesai dengan URL `https://inovasikepegawaian.vercel.app`.

- [ ] **Step 5: Verifikasi boot**

Via `vercel get_deployment_build_logs` → pastikan build sukses, tidak ada error import. Via `web_fetch_vercel_url` → GET `/` → 200 (form tampil; app tidak crash walau belum login).

---

### Task 7: E2E browser — verifikasi alur + bersihkan data test + kirim link

**Files:** tidak ada (verifikasi manual via playwright / skill webapp-testing)

**Interfaces:**
- Consumes: URL production `https://inovasikepegawaian.vercel.app`.
- Produces: bukti alur pegawai & staff jalan; data test dihapus; link final untuk user.

- [ ] **Step 1: Buka form & submit pengajuan test**

Via Playwright:
- Navigasi `https://inovasikepegawaian.vercel.app/`
- Isi `nama = "__TEST__"`, pilih UPTD, jenis cuti, tanggal mulai/selesai, upload file kecil (buat `test-berkas.txt` — tapi ekstensi harus di `ALLOWED_EXTENSIONS`; buat `test-berkas.pdf` minimal atau JPEG).
- Submit → assert pesan sukses + nomor `CUT-2026-XXXX`.

- [ ] **Step 2: Cek status pegawai**

- `/status` → cari `__TEST__` → row muncul.

- [ ] **Step 3: Login staff & kelola**

- `/login` → `STAFF_PASSWORD` → masuk dashboard.
- Dashboard: `__TEST__` muncul sebagai `Baru`, baris valid (is_late menghitung benar).
- Detail: unduh berkas → status dipindah ke "Diproses".
- Logout.

- [ ] **Step 4: Akses anonym ditolak untuk dashboard/berkas**

- Tanpa login: `/staff` → redirect `/login`; `/uploads/<filename>` → redirect `/login`.

- [ ] **Step 5: Bersihkan data test**

Via `supabase execute_sql`:
```sql
delete from cuti where nama = '__TEST__';
```
Hapus file dari storage (via Python/`supabase-py` lokal memakai env, atau manual dashboard Supabase Storage → `berkas` → hapus object test).

- [ ] **Step 6: Verifikasi dashboard bersih**

- `/login` → dashboard → tidak ada baris `__TEST__`.

- [ ] **Step 7: Kirim link final ke user**

Berikan:
```
https://inovasikepegawaian.vercel.app
```
Serta catatan: pegawai klik link → isi form (tanpa login); admin buka `/login`.