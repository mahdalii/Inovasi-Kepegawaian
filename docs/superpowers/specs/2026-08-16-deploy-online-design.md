# Spec: Deploy Online — Sistem Pengajuan Cuti (Inovasi Kepegawaian)

Tanggal: 2026-08-16
Status: Disetujui user (Mahdali)

## Tujuan

Sistem pengajuan cuti pegawai yang sekarang jalan di komputer kantor
(Flask + SQLite lokal) dipindah ke internet supaya pegawai bisa isi form
dari mana saja lewat satu link.

- Pegawai: klik link → isi form cuti → dapat nomor pengajuan. Tanpa login.
- Admin (hanya Mahdali): `/login` dengan satu kata sandi → dashboard,
  ubah status, unduh berkas.
- Sesuai keputusan user: **mulai baru** — data lama di `cuti.db` lokal TIDAK
  dipindah. Riwayat lama tetap hidup di komputer kantor.

## Arsitektur

| Lapisan | Pilihan |
|---|---|
| Hosting | Vercel (serverless, Free plan) |
| Database | Supabase Postgres (project `lidxvlxfvtdhzaermgvi`, region ap-northeast-1, sudah aktif) |
| Berkas upload | Supabase Storage, bucket `berkas` |
| URL | `https://inovasikepegawaian.vercel.app` |

Alasan: Vercel free & sudah terhubung (MCP). Supabase free tier cukup untuk
volume satu kantor. Serverless tidak mendukung SQLite ephemal → pindah
Postgres. File upload butuh persistent storage → Supabase Storage.

## Skema Database (Postgres)

Sama dengan skema SQLite lama, ditambah tabel counter untuk nomor urut
(di SQLite nomor dibuat dari `COUNT`; di Postgres pakai counter agar tetap
urut dan aman di bawah konkurensi):

```sql
create table cuti (
  id bigint generated always as identity primary key,
  nomor text not null unique,
  nama text not null,
  uptd text not null,
  jenis text not null,
  tgl_mulai text not null,
  tgl_selesai text not null,
  berkas text not null,        -- nama object di Storage (uuid.ext)
  status text not null default 'Baru',
  catatan text not null default '',
  tgl_masuk text not null
);

create table counter (
  id integer primary key,       -- selalu 1
  tahun text not null,          -- '2026'
  nilai integer not null
);
```

`gen_nomor`: ambil counter untuk tahun berjalan, increment, pakai angka itu
(`CUT-2026-0001`). Gagal karena konflik → ulang. (Ponytail: satu baris
counter cukup untuk volume kantor; upgrade ke sequence per-tahun hanya kalau
diperlukan.)

## Alur

1. Pegawai buka URL → `/` (form, tanpa auth — sama seperti sekarang)
2. Submit: validasi di server → upload berkas ke bucket `berkas` (key dari
   `safe_filename`, uuid) → insert row `cuti` (berkas = nama object)
   → kalau insert gagal, hapus object yang baru diupload
3. Cek status → `/status` (public, sama seperti sekarang)
4. Admin login `/login` → session cookie (`SECRET_KEY` dari env)
   - `/staff` dashboard: filter UPTD/status, cari, baris merah jika terlambat
   - `/staff/<id>`: ubah status, tulis catatan
   - `/uploads/<filename>`: download dari Storage (wajib login, sama dulu)

Status transisi & `is_late` tidak berubah sama sekali (logika murni,
tetap `app.py`).

## Konfigurasi

- `config.py`: DB/Storage URL diambil dari env vars
  - `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (server-side only — dipakai
    backend, TIDAK pernah ke browser; service role key disimpan di env Vercel)
  - `STAFF_PASSWORD` (sudah ada)
  - `SECRET_KEY` (sudah ada)
- Vercel: set env vars via dashboard/CLI
- `.gitignore` tambah file token lokal kalau ada

Catatan keamanan: `SUPABASE_SERVICE_ROLE_KEY` = akses penuh DB. Hanya ada
di env Vercel, tidak pernah dirender ke client. Supabase Storage bucket
`berkas` di-lock: tidak ada akses publik, semua baca lewat backend
(`/uploads/...` yang sudah paksa login staff).

## Perubahan File

- `app.py` — `get_conn` → `get_supabase()`; `gen_nomor`/`save_pengajuan`/query
  route diadaptasi ke Postgres; `unduh_berkas` baca dari Storage
- `config.py` — env vars baru
- `test_app.py` — adaptasi: fungsi murni (`is_late`, `can_transition`,
  `validate_form`) tetap test offline; test DB ganti ke Supabase test yang
  sudah ada (project aktif, free) dengan fixture pembersihan
- `requirements.txt` — tambah `supabase`
- `vercel.json` — route + build
- Baru: `api/index.py` (entry WSGI → serverless), atau pakai Gunicorn build
  paket — diputuskan saat planning

Tidak berubah: `templates/*` (tombol/semua label sama), alur status,
validasi form.

## Error Handling & Rollback

- Upload berkas → kemudian insert DB gagal → hapus berkas dari Storage
  (pola sama dengan `save_pengajuan` yang sekarang menghapus file lokal)
- Insert gagal karena nomor bentrok → retry (sudah ada, dipertahankan)
- Storage down → tampilkan pesan error yang jelas, jangan simpan row
  tanpa berkas

## Pengujian

1. `pytest test_app.py` — logika murni offline + test DB di Supabase dev.
   Gagal jika Supabase offline → test DB pakai project yang sama (sudah
   diputuskan, bukan project terpisah).
2. Manual via browser (skill webapp-testing / playwright):
   - Submit form nyata (dengan file) → nomor muncul
   - `/status` cari nomor → muncul
   - Login → dashboard → lihat row baru → unduh berkas → ubah status
   - Cek status tablet/HP viewport
3. Data test dihapus setelah verifikasi (supaya DB online bersih untuk
   pemakaian asli)

## Di Luar Cakupan (sengaja)

- Migrasi data lama dari `cuti.db` → diputuskan "mulai baru"
- Fitur baru apa pun (email, notifikasi, multi-admin, roles) — tidak ditanya,
  tidak dibuat
- Auth pegawai — pegawai tanpa login (sesuai desain lama & permintaan admin
  tunggal)