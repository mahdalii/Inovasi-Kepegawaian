@echo off
rem ============================================================
rem  CARA PAKAI (untuk petugas kantor):
rem  1. Buka file ini dengan Notepad.
rem  2. Ganti kata "sandi-anda" di bawah ini dengan sandi sendiri,
rem     lalu simpan.
rem  3. Klik 2x file ini. Aplikasi langsung jalan dan browser
rem     otomatis terbuka.
rem  4. Untuk berhenti: tekan Ctrl+C pada jendela hitam ini.
rem ============================================================
cd /d "%~dp0"

set STAFF_PASSWORD=sandi-anda

start "" http://127.0.0.1:5000
.venv\Scripts\python.exe app.py

pause