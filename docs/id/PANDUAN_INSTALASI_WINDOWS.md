# Panduan Instalasi dan Pengaturan Sistem pada Windows

## Prosedur Cepat 6 Langkah Menjalankan HydroMT-SFINCS Mandiri bagi Anggota Tim

> **Versi Bahasa:** Bahasa Indonesia | [English Version](../WINDOWS_INSTALLATION_GUIDE.md)

Panduan ini disusun sebagai petunjuk teknis bagi anggota tim untuk menyiapkan dan menjalankan **Model Bahaya Banjir 2D Provinsi Sumatera Barat** pada komputer bersistem operasi Windows (Windows 10 maupun Windows 11) tanpa memerlukan Git, Conda, maupun hak akses administrator.

---

## Alur Kerja Cepat 6 Langkah (Tanpa Git)

```mermaid
graph LR
    S1[1. Pasang VS Code] --> S2[2. Salin Folder Proyek]
    S2 --> S3[3. Buka Folder di VS Code]
    S3 --> S4[4. Jalankan Skrip Instalasi]
    S4 --> S5[5. Pilih Kernel Notebook]
    S5 --> S6[6. Jalankan Sel Notebook]
```

### Langkah 1: Pasang Visual Studio Code
* Unduh dan pasang perangkat lunak **Visual Studio Code (VS Code)** melalui situs resmi [https://code.visualstudio.com/](https://code.visualstudio.com/).
* Buka VS Code, pilih menu **Extensions** (`Ctrl + Shift + X`), lalu cari dan pasang dua ekstensi berikut:
  * **Python** (penerbit: Microsoft)
  * **Jupyter** (penerbit: Microsoft)

### Langkah 2: Salin Folder Proyek ke Komputer Lokal
* Salin folder `sumbar_flood_hazard` (melalui media penyimpanan eksternal, jaringan lokal, atau arsip `.zip`) ke diska lokal komputer Anda.
* Contoh lokasi penyimpanan yang disarankan: `D:\Project\sumbar_flood_hazard` atau `C:\Project\sumbar_flood_hazard`.
* Hindari meletakkan folder proyek di dalam folder yang tersinkronisasi otomatis seperti OneDrive untuk mencegah penguncian berkas GeoPackage dan log saat simulasi berlangsung.

### Langkah 3: Buka Folder Proyek di VS Code
* Pada jendela VS Code, klik **File** -> **Open Folder...** -> pilih folder `D:\Project\sumbar_flood_hazard`.

### Langkah 4: Jalankan Skrip Pengaturan Lingkungan Otomatis pada Terminal VS Code
* Buka terminal bawaan di VS Code (`Ctrl + ` ` ` atau klik **Terminal** -> **New Terminal**).
* Salin dan jalankan satu perintah berikut:
  ```powershell
  powershell -ExecutionPolicy Bypass -File .\env\setup_env.ps1
  ```
  *(Skrip ini secara otomatis memasang pengelola paket `uv`, menyiapkan **Python 3.12** terisolasi, memasang seluruh pustaka geospasial dalam waktu kurang dari 60 detik, membuka blokir berkas biner pada Windows 11, serta mendaftarkan kernel Jupyter).*

### Langkah 5: Buka Notebook dan Pilih Kernel yang Tepat
* Buka berkas notebook utama pada [`notebook/master/01_sfincs_flood_hazard_run.ipynb`](../../notebook/master/01_sfincs_flood_hazard_run.ipynb).
* Pada sudut kanan atas editor notebook, klik tombol **Select Kernel**:
  * Pilih **Python Environments...** -> pilih **`.venv`** (`.\.venv\Scripts\python.exe`).
  * *(Atau pilih **Jupyter Kernel...** -> **`HydroMT-SFINCS`**).*

> [!IMPORTANT]
> **Pencegahan galat "No module named pyproj":** Saat VS Code membuka notebook untuk pertama kali, sistem sering kali memilih instalasi Python global pada Windows secara bawaan. Pastikan tombol kernel di sudut kanan atas selalu menampilkan **`.venv`** atau **`HydroMT-SFINCS`** sebelum menjalankan sel apa pun.

### Langkah 6: Atur Klaster DAS Tugas Anda dan Jalankan Simulasi
* Pada **Sel 1 (Panel Kendali Konfigurasi Pengguna)**, tentukan kode klaster DAS dan kala ulang yang ditugaskan kepada Anda:
  ```python
  SELECTED_CLUSTERS = ["DAS_104"]  # Ubah sesuai kode DAS tugas Anda (contoh: DAS_101 hingga DAS_114)
  SELECTED_RPS = ["rp100"]         # Pilihan: "rp2", "rp5", "rp10", "rp25", "rp50", "rp100"
  ```
* Jalankan **Sel 2 (Verifikasi Lingkungan dan Data)** untuk memastikan jalur PROJ/GDAL terhubung dengan benar dan modul `sfincs_standalone_pipeline` termuat sempurna.
* Jalankan sel-sel berikutnya secara berurutan atau klik **Run All**.

---

## Spesifikasi Perangkat Lunak dan Pustaka Pendukung

Alur kerja ini distandardisasi pada **Python 3.12** yang dikelola menggunakan **`astral-sh/uv`** agar lingkungan virtual bersifat konsisten, cepat, dan ringan tanpa ketergantungan Conda:

| Kategori | Komponen / Pustaka | Spesifikasi Versi | Fungsi dalam Alur Kerja |
| :--- | :--- | :--- | :--- |
| **Runtime** | Python | `3.12.x` (64-bit) | Mesin eksekusi utama |
| **Pengelola Paket** | `uv` | Versi terbaru | Pengelola lingkungan virtual `.venv` dan paket |
| **Mesin Hidrodinamika** | Berkas Biner SFINCS | `2.4.0-galibier-release` | Penyelesai aliran permukaan 2D dan subkisi |
| **Pembangun Model** | `hydromt` | `==0.10.1` | Kerangka inti HydroMT |
| **Plugin Model** | `hydromt-sfincs` | `==1.2.2` | Pembangkit kisi dan tabel subkisi SFINCS |
| **Pengolah Vektor** | `geopandas` | `>=1.0.0` (1.1.x) | Pengolahan batas DAS, sungai, dan administrasi |
| **Pengolah Raster** | `rasterio` | `>=1.4.0` (1.5.x) | Pembacaan, penulisan GeoTIFF, dan penurunan skala |
| **Proyeksi / CRS** | `pyproj` | `>=3.7.0` (3.7.x) | Transformasi sistem koordinat PROJ secara dinamis |
| **Array Spasial** | `xarray` / `rioxarray` | `>=2024.1.0` / `>=0.18.0` | Pembacaan NetCDF hujan rancangan dan kubus data |
| **Kisi Tidak Terstruktur** | `xugrid` | `>=0.14.0` | Operasi kisi spasial HydroMT |
| **Arah Aliran** | `pyflwdir` | `>=0.5.10` | Ekstraksi jaringan sungai dan arah aliran |
| **Visualisasi** | `matplotlib` / `folium` | `>=3.9.0` / `>=0.17.0` | Peta verifikasi 3 panel dan peta web interaktif |
| **Animasi** | `pillow` / `imageio` | `>=10.0.0` | Penyusunan animasi GIF perambatan banjir |

---

## Pengaturan Manual (PowerShell Langkah demi Langkah)

Apabila Anda memilih menjalankan perintah instalasi secara manual tanpa menggunakan `setup_env.ps1`:

```powershell
# 1. Pasang pengelola paket astral-sh/uv
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Perbarui variabel PATH pada sesi terminal aktif
$env:Path += ";$HOME\.local\bin;$HOME\.cargo\bin"

# 2. Bentuk lingkungan virtual terpadu (.venv) dari pyproject.toml dan uv.lock
uv sync --extra dev

# 3. Daftarkan kernel Jupyter untuk VS Code
.\.venv\Scripts\python.exe -m ipykernel install --user --name hydromt-sfincs --display-name "HydroMT-SFINCS"
```

---

## Verifikasi Mesin SFINCS Asli dan Pustaka DLL

Pastikan berkas eksekusi hidrodinamika SFINCS 64-bit dapat dijalankan dengan baik melalui PowerShell:

```powershell
.\bin\sfincs.exe
```

**Keluaran yang Diharapkan:**
```text
 ******************************************************************************
 *                                                                            *
 * SFINCS: Super-Fast INundation of CoastS and riverS                         *
 *                                                                            *
 * Deltares, The Netherlands                                                  *
 * Version 2.4.0-galibier-release                                             *
 ******************************************************************************
```
*(Apabila tampilan di atas muncul, seluruh pustaka pendukung Intel Fortran, OpenMP, HDF5, dan NetCDF di dalam folder `bin/` telah berfungsi penuh).*

---

## Urutan Eksekusi Sel pada Notebook Utama

Saat menjalankan [`notebook/master/01_sfincs_flood_hazard_run.ipynb`](../../notebook/master/01_sfincs_flood_hazard_run.ipynb), jalankan seluruh sel secara berurutan:

* **Sel 1 (Panel Kendali Konfigurasi Pengguna):** Menentukan klaster DAS sasaran dan kala ulang (misalnya `SELECTED_CLUSTERS = ["DAS_104"]`, `SELECTED_RPS = ["rp100"]`).
* **Sel 2 (Verifikasi Lingkungan dan Data):** Menghubungkan jalur PROJ/GDAL secara dinamis dari lingkungan virtual aktif serta memuat modul `sfincs_standalone_pipeline`.
* **Sel 3 / Tahap 1 (Pembangunan Kisi Dasar SFINCS):** Membangun domain komputasi terbatasi DAS pada resolusi baku **80 m (V3)** (atau opsi 40 m), membentuk tabel subkisi 10 m secara langsung dari FABDEM 30 m asli, melakukan pembakaran alur sungai dengan dukungan `rivers_ar.gpkg`, serta memetakan kekasaran permukaan Manning dari Penutup Lahan RBI BIG.
* **Sel 4 / Tahap 2 (Pemaksaan Hujan Langsung, Infiltrasi CNB, dan Pasang Surut MHHW):** Menerapkan hidrograf hujan rancangan 24 jam (`rainfall_<rp>.nc`) beserta periode resesi nol hujan dinamis (24 hingga 48 jam), menyuntikkan infiltrasi `CNB` USDA-NRCS (`smaxfile`, `sefffile`, `ksfile`), serta menetapkan batas pasang surut pesisir MHHW `+0,80 m` pada DAS pesisir.
* **Sel 5 / Tahap 3 (Eksekusi Mesin Simulasi Hidrodinamika SFINCS):** Menjalankan penyelesai 2D dilengkapi bilah progres interaktif (memilih otomatis `bin/sfincs.exe` atau cadangan Docker).
* **Sel 6 / Tahap 4 (Pengolahan Pascasimulasi Hidrostatis Ketat [Minimum 15 cm], QA Subkisi, dan Klasifikasi BNPB):** Menurunkan skala elevasi muka air ke resolusi 10 m, menghapus seluruh piksel dengan kedalaman di bawah **ambang minimum `0,15 m` (`15 cm`)** pada raster Kedalaman, Indeks Bahaya, dan Kelas Bahaya, menerapkan pemulihan tepi `bilinear edge-NaN` murni tanpa penambahan tinggi air sintetis (`freeboard_m=0.0`, jarak `<= 80 m`, `bridge_radius=3`) serta ambang kebersihan 4 arah `30 m x 30 m` (`hole_mmu_ha=1.0`), menghitung kelas bahaya resmi **Peraturan Kepala BNPB Nomor 02 Tahun 2012** beserta surogat **Indeks Bahaya Banjir (0 hingga 1)**, serta menjalankan audit QA hipsometri subkisi dan validasi survei QField.
* **Sel 7 / Tahap 5 (Visualisasi Peta Hasil dan QA/QC):** Menampilkan gambar verifikasi 3 panel siap publikasi (Peta Kedalaman Genangan 10 m, Indeks Bahaya Kontinu, dan Peta 3 Kelas Bahaya BNPB).
* **Sel 8 / Tahap 6 (Animasi Perambatan Gelombang Banjir):** Menyusun dinamika genangan per jam menjadi berkas animasi GIF (`DASXXX_RPYYY_Flood_Animation.gif`).

---

## Pemeriksaan Berkas Keluaran

Setelah notebook selesai dijalankan, seluruh produk keluaran tersimpan secara terstruktur pada direktori `outputs/{das_id}/{rp}/`:

```text
outputs/DAS_104/rp100/
├── DAS104_RP100_Flood_Depth.tif          <- Kedalaman genangan maksimum terhaluskan secara hidrostatis (m)
├── DAS104_RP100_Flood_Depth_raw.tif      <- Kedalaman hasil penurunan skala mentah sebelum penyaringan (m)
├── DAS104_RP100_FloodHazard_Index.tif    <- Indeks Bahaya Banjir kontinu Fuzzy Large (0,0 hingga 1,0) + .qml
├── DAS104_RP100_FloodHazard_Classes.tif  <- Kelas Bahaya Perka BNPB No. 02/2012 (1: Rendah, 2: Sedang, 3: Tinggi) + .qml
├── qa_report.json                        <- Laporan kendali mutu otomatis (kekasaran, batas, puncak, volume)
└── survey_validation.json                <- Hasil validasi terhadap titik observasi lapangan QField
```

Buka berkas GeoTIFF tersebut menggunakan perangkat lunak **QGIS** untuk meninjau sebaran genangan dan menyusun tata letak peta tematik kebencanaan.

---

## Penanganan Masalah Umum (Troubleshooting)

| Permasalahan | Penyebab | Solusi |
| :--- | :--- | :--- |
| **`No module named pyproj`** atau **`ModuleNotFoundError`** | Notebook VS Code terhubung ke Python global Windows, bukan lingkungan virtual `.venv`. | Klik **Select Kernel** di sudut kanan atas -> **Python Environments...** -> pilih **`.venv`** (atau **Jupyter Kernel...** -> **`HydroMT-SFINCS`**). |
| **`Running scripts is disabled on this system`** | Kebijakan eksekusi skrip PowerShell pada Windows masih terbatas. | Jalankan perintah: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| **Kernel `HydroMT-SFINCS` tidak tampil di VS Code** | VS Code masih menyimpan tembolok (*cache*) daftar kernel lama. | Tekan `Ctrl + Shift + P` -> pilih `Developer: Reload Window`. |
| **`sfincs.exe exited with code 3221225781`** | Runtime Microsoft Visual C++ 2015 sampai 2022 atau pustaka DLL Intel Fortran belum lengkap. | Pasang [vc_redist.x64.exe](https://aka.ms/vs/17/release/vc_redist.x64.exe) dan pastikan seluruh 9 berkas DLL tetap berada di folder `bin/`. |
| **`PermissionError: [WinError 5] Access is denied` pada `sfincs.exe`** | Fitur Windows 11 SmartScreen / *Mark-of-the-Web* memblokir berkas biner hasil salinan jaringan. | Jalankan di PowerShell: `Get-ChildItem -Path .\bin -Recurse \| Unblock-File` (atau jalankan ulang `.\env\setup_env.ps1`). |
| **`PermissionError: [WinError 32]` pada `hydromt.log`** | Berkas log masih terkunci oleh sesi kernel Jupyter sebelumnya atau aplikasi lain. | Klik tombol **Restart** pada bilah atas notebook (atau tutup jendela QGIS/editor yang membuka folder model), lalu jalankan ulang mulai dari Sel 1. |
| **`ImportError: DLL load failed while importing _gdal`** | Konflik jalur pustaka PROJ atau GDAL (sering terjadi apabila QGIS terpasang di PATH sistem). | Pastikan Anda menggunakan kernel `.venv` (`HydroMT-SFINCS`) dan telah menjalankan Sel 2 notebook. |
| **Memori (RAM) penuh saat pembangunan kisi** | Proses pemotongan raster FABDEM beresolusi tinggi saat ekstraksi subkisi 10 m. | Pastikan tersedia minimal 8 GB RAM bebas; tutup peramban web atau aplikasi latar belakang yang tidak diperlukan. |
