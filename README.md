# Sistem Pengajuan Cuti (Inovasi Kepegawaian)

Aplikasi antrian pengajuan cuti pegawai agar tidak ada pengajuan yang tenggelam.
Dibuat sesederhana mungkin: pengisi (termasuk orangtua) hanya perlu **klik
link, lalu langsung mengisi formulir** — tidak perlu install apa-apa.

## Cara Paling Mudah (untuk petugas kantor)

1. Buka `start_aplikasi.bat` dengan Notepad, ganti `sandi-anda` menjadi sandi
   sendiri, simpan. (Hanya perlu dilakukan sekali.)
2. Klik 2x `start_aplikasi.bat` — aplikasi jalan & browser terbuka sendiri.
3. Bagikan link ke pegawai/orangtua lewat WhatsApp (lihat bagian di bawah).

## Bagikan Link ke Pegawai

Saat aplikasi sedang jalan, bagikan alamat berikut lewat WhatsApp:

```
http://<IP-KOMPUTER>:5000
```

- Cari IP: buka Command Prompt, ketik `ipconfig`, ambil baris "IPv4 Address"
  (contoh: `192.168.1.25`), lalu ganti `<IP-KOMPUTER>` dengan angka itu.
- Contoh teks WhatsApp yang bisa disalin:
  > Assalamualaikum Bapak/Ibu, untuk mengajukan cuti silakan klik link ini,
  > isi formulirnya (cukup 6 pertanyaan, kurang dari 2 menit). Terima kasih.
  > http://192.168.1.25:5000
- Pegawai cukup klik link → langsung muncul formulir. Nomor pengajuan
  (contoh: CUT-2026-0001) otomatis tampil setelah kirim — minta mereka
  mencatatnya atau memfotonya untuk cek status nanti.
- Pegawai di luar kantor (tidak satu jaringan Wi-Fi) tidak bisa membuka link
  ini karena aplikasi hanya hidup di jaringan kantor.

## Menjalankan (cara teknis)

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

Atau ganti `sandi-anda` di file `start_aplikasi.bat` lalu klik 2x file itu
(cara yang lebih mudah untuk petugas kantor).

## Backup

Salin 2 hal: file `cuti.db` dan folder `uploads/`.

Catatan pembaruan: bila menjalankan versi baru ini di atas instalasi lama,
hapus `cuti.db` sekali (struktur database berubah — NIP diganti UPTD PPD,
tidak ada mekanisme migrasi otomatis).

## Pengujian

```
pytest test_app.py -v
```

## Cara Pakai Ringkas

- Pegawai → halaman utama: isi form (nama + UPTD PPD + jenis cuti), dapat nomor `CUT-2026-XXXX`.
- Pegawai → "Cek Status": masukkan nomor pengajuan atau nama.
- Staff → /login → dashboard: filter UPTD & status, cari nama/nomor, baris merah = pengajuan > 2 hari belum selesai.
- Staff → detail: unduh berkas, ubah status, tulis catatan.
