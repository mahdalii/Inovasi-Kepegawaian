# Desain: Sistem Antrian Pengajuan Cuti Kepegawaian

Tanggal: 2026-08-13
Status: Disetujui oleh pemilik proyek

## 1. Latar Belakang & Masalah

Bagian kepegawaian kantor pemerintah menerima pengajuan cuti pegawai melalui
WhatsApp. Berkas pengajuan (form persetujuan atasan, bukti sakit, bukti alasan
penting) sering tenggelam di chat sehingga pengajuan ketimbun dan baru
diproses ketika pegawai menagih. Skala kantor besar (200+ pegawai, pengajuan
cuti banyak per bulan).

Tujuan inovasi: **tidak ada pengajuan cuti yang tenggelam**.

Pembuatan nota dinas TIDAK termasuk ruang lingkup — sudah ada aplikasi khusus
yang terintegrasi.

## 2. Alur Kerja

```
Pegawai                     Bagian Kepegawaian
   │                                │
   ├─ Buka form (LAN/Wi-Fi kantor)  │
   ├─ Pilih jenis cuti              │
   │   ├─ Tahunan: upload form      │
   │   │   persetujuan atasan       │
   │   ├─ Sakit: upload bukti sakit │
   │   └─ Alasan Penting: upload    │
   │       bukti alasan penting     │
   ├─ Isi tanggal mulai–selesai     │
   └─ Kirim → dapat nomor           ├─ Buka Dashboard Antrian
       pengajuan                     ├─ Lihat semua pengajuan terurut
                                    ├─ Unduh berkas, ubah status, catatan
                                    └─ (nota dinas dibuat di aplikasi lain)
```

Status: `Baru → Diproses → Disetujui` atau `Baru → Diproses → Ditolak` (nilai status: Baru, Diproses, Disetujui, Ditolak)

## 3. Halaman Aplikasi

1. **Form Pegawai** — Nama, NIP, jenis cuti (tahunan/sakit/alasan penting),
   tanggal mulai–selesai, upload berkas (label menyesuaikan jenis cuti), kirim.
   Setelah kirim tampil nomor pengajuan.
2. **Cek Status Pegawai** — input NIP, tampilkan semua pengajuan + statusnya.
3. **Dashboard Staff** — tabel semua pengajuan: NIP, nama, jenis, tanggal cuti,
   tanggal masuk, umur pengajuan, status. Pengajuan yang masih `Baru`/`Diproses`
   lebih dari 2 hari disorot merah + muncul di daftar "Perlu Perhatian". Ada
   pencarian & filter.
4. **Detail Pengajuan** — unduh berkas, ubah status, tulis catatan.

## 4. Aturan Logika

- Ambang "terlambat": > 2 hari kalender sejak tanggal masuk dan status masih
  `Baru` atau `Diproses` (belum sampai Disetujui/Ditolak).
  (Catatan: memakai hari kalender untuk kesederhanaan; disesuaikan di revisi
  jika kantor minta hari kerja.)
- NIP dianggap unik per pegawai; satu pegawai boleh punya banyak pengajuan.
- Status hanya bisa bergerak maju: Baru → Diproses → Disetujui / Ditolak.

## 5. Teknologi

- Python + Flask + SQLite (satu database file lokal)
- Jalan di 1 komputer kantor: `http://<ip-komputer>:5000`
- Backup = salin file database
- Gratis, tanpa langganan, data tetap di kantor

## 6. Keamanan & Batasan Upload

- Dashboard staff dilindungi kata sandi tunggal (dikonfigurasi di file config)
- Halaman pegawai terbuka tanpa login
- Upload: hanya PDF/JPG/PNG, maks 5 MB

## 7. Pengujian

- Pengujian otomatis kecil (unittest) untuk:
  - Ambang keterlambatan: > 2 hari dan status masih `Baru`/`Diproses`
  - Alur status tidak bisa mundur
  - Validasi form (file wajib, ukuran file, tanggal wajib)

## 8. Tampilan Visual & Animasi

- Tampilan bersih dan modern (CSS sendiri, tanpa framework berat).
- Animasi dengan CSS murni (tanpa perpustakaan JS tambahan):
  - Halaman pegawai: fade-in setelah kirim, tombol dengan efek tekan.
  - Dashboard: baris pengajuan baru muncul dengan animasi ringan; baris yang
    "terlambat" berdenyut halus (pulse) agar langsung menarik mata.
  - Badge status berwarna (Biru = Baru, Kuning = Diproses, Hijau = Disetujui,
    Merah = Ditolak) dengan transisi lembut.
- Mendukung mode terang/gelap otomatis (media query).

## 9. Di Luar Ruang Lingkup

- Generate nota dinas (aplikasi khusus sudah ada)
- Autentikasi pegawai (cukup NIP)
- Integrasi WhatsApp
- Dashboard statistik lengkap (cukup filter & pencarian)
