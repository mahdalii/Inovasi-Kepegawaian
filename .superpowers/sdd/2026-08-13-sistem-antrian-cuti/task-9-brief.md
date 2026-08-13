### Task 9: Hapus NIP, tambah field UPTD PPD + pencarian nama/nomor

**Files:**
- Modify: `app.py` (SCHEMA_SQL, VALID_JENIS area, validate_form, save_pengajuan, create_app: rute status & dashboard & detail)
- Modify: `templates/form.html`, `templates/status.html`, `templates/dashboard.html`, `templates/detail.html`
- Modify: `test_app.py`
- Modify: `README.md`

**Perubahan persyaratan (dari pengguna):**
1. NIP dihapus TOTAL dari sistem (privacy — khawatir data NIP tersebar).
2. Form pegawai menjadi: **Nama**, **UPTD PPD** (dropdown 10 pilihan), **Jenis Cuti**, tanggal mulai-selesai, upload berkas.
3. Cek status: satu kolom pencarian — pegawai memasukkan **nomor pengajuan ATAU nama**.
4. Dashboard: pencarian (nomor/nama), filter UPTD + filter status.

**Daftar UPTD PPD (10 nilai, gunakan persis):**
`batam_centre`, `batuaji`, `tanjungpinang`, `bintan`, `kijang`, `natuna`, `anambas`, `karimun`, `tanjungbatu`, `lingga`

Label tampilan: "Batam Centre", "Batuaji", "Tanjungpinang", "Bintan", "Kijang", "Natuna", "Anambas", "Karimun", "Tanjungbatu", "Lingga"

---

- [ ] **Step 1: Update SCHEMA_SQL di app.py**

Ganti kolom `nip TEXT NOT NULL` dengan `uptd TEXT NOT NULL` (posisi yang sama, sebelum `jenis`). Kolom baru: `id, nomor, nama, uptd, jenis, tgl_mulai, tgl_selesai, berkas, status, catatan, tgl_masuk`.

- [ ] **Step 2: Tambah UPTD_LABEL + VALID_UPTD di app.py**

```python
VALID_UPTD = {"batam_centre", "batuaji", "tanjungpinang", "bintan", "kijang",
              "natuna", "anambas", "karimun", "tanjungbatu", "lingga"}

UPTD_LABEL = {
    "batam_centre": "Batam Centre", "batuaji": "Batuaji",
    "tanjungpinang": "Tanjungpinang", "bintan": "Bintan", "kijang": "Kijang",
    "natuna": "Natuna", "anambas": "Anambas", "karimun": "Karimun",
    "tanjungbatu": "Tanjungbatu", "lingga": "Lingga",
}
```

- [ ] **Step 3: Update validate_form**

Ubah parameter `nip` → `uptd`. Validasi: nama wajib, `uptd in VALID_UPTD` (pesan "UPTD PPD tidak valid" / "UPTD PPD wajib diisi"), jenis valid, tanggal, berkas, ukuran. Update test yang memanggilnya.

- [ ] **Step 4: Update save_pengajuan**

Signature menjadi `save_pengajuan(conn, nama, uptd, jenis, tgl_mulai, tgl_selesai, berkas, tgl_masuk)`. INSERT kolom uptd (bukan nip).

- [ ] **Step 5: Update rute form_pegawai (POST)**

Ambil `request.form.get("uptd", "")`, kirim ke validate_form dan save_pengajuan. Konteks template tambah `uptd_labels=UPTD_LABEL`.

- [ ] **Step 6: Update rute status — pencarian nomor ATAU nama**

```python
    @app.route("/status", methods=["GET", "POST"])
    def status():
        rows, q = [], request.form.get("q", "")
        if request.method == "POST":
            conn = get_conn()
            rows = conn.execute(
                "SELECT * FROM cuti WHERE nomor LIKE ? OR nama LIKE ? "
                "ORDER BY tgl_masuk DESC, id DESC",
                (f"%{q.strip()}%", f"%{q.strip()}%"),
            ).fetchall()
            conn.close()
        return render_template("status.html", rows=rows, q=q,
                               jenis_labels=JENIS_LABEL, uptd_labels=UPTD_LABEL)
```

- [ ] **Step 7: Update rute dashboard**

- q mencari `nama LIKE ? OR nomor LIKE ?` (hapus nip)
- Tambah filter UPTD: parameter `uptd` dari `request.args`, `AND uptd=?`
- Konteks: tambah `uptds=VALID_UPTD`, `filter_uptd`, `uptd_labels`

- [ ] **Step 8: Update rute detail**

Halaman detail menampilkan UPTD (bukan NIP): `uptd_labels[row["uptd"]]`. Konteks tambah `uptd_labels`.

- [ ] **Step 9: Update templates**

- `form.html`: hapus input NIP; tambah dropdown UPTD (sebelum jenis cuti):
  ```html
  <label>UPTD PPD
    <select name="uptd" required>
      <option value="">— pilih UPTD —</option>
      {% for k, v in uptd_labels.items() %}
      <option value="{{ k }}">{{ v }}</option>
      {% endfor %}
    </select>
  </label>
  ```
  (jika ada error 400, repopulate pilihan dengan `{% if data and data.uptd == k %}selected{% endif %}` — perbaiki juga masalah repopulate select jenis yang sudah dicatat sebagai deferred minor)
- `status.html`: ganti input NIP jadi satu kolom pencarian `name="q"` placeholder "Masukkan nomor pengajuan atau nama"
- `dashboard.html`: kolom NIP → kolom UPTD (`{{ uptd_labels[row.uptd] }}`); tambah dropdown filter UPTD di samping filter status; hapus referensi nip
- `detail.html`: baris NIP → baris UPTD

- [ ] **Step 10: Update test_app.py**

- `test_save_pengajuan_tersimpan_dan_status_baru`: ganti argumen nip → uptd ("batam_centre"), verifikasi `row["uptd"]`
- `test_validate_form_menolak_data_tidak_lengkap`: argumen nip "123" → uptd "haha" (invalid); tambah cek error UPTD; argumen valid uptd di test lain
- Semua pemanggilan validate_form/save_pengajuan diperbarui
- Jalankan `python -m pytest test_app.py -v` — semua lulus

- [ ] **Step 11: Update README.md**

- Bagian "Cara Pakai Ringkas": form = nama + UPTD + jenis cuti (tanpa NIP); cek status = nomor/nama; dashboard filter UPTD
- Sesuaikan kalimat yang menyebut NIP

- [ ] **Step 12: Uji manual end-to-end**

Jalankan `python app.py`:
1. Submit form dengan nama + UPTD + file → nomor muncul, row tersimpan dengan uptd benar
2. Cek status dengan NAMA → muncul; dengan NOMOR → muncul
3. Login staff → dashboard: filter UPTD bekerja, pencarian nama/nomor bekerja
4. Detail: UPTD tampil, unduh berkas, ubah status
5. Matikan server, hapus data uji (cuti.db, uploads selain .gitkeep), pastikan `git status` bersih
