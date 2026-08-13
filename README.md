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

- Pegawai → halaman utama: isi form (nama + UPTD PPD + jenis cuti), dapat nomor `CUT-2026-XXXX`.
- Pegawai → "Cek Status": masukkan nomor pengajuan atau nama.
- Staff → /login → dashboard: filter UPTD & status, cari nama/nomor, baris merah = pengajuan > 2 hari belum selesai.
- Staff → detail: unduh berkas, ubah status, tulis catatan.
