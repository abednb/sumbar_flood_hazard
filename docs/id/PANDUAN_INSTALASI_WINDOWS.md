# Panduan Instalasi dan Setup pada Windows

## Prosedur Cepat 6 Langkah Menjalankan HydroMT-SFINCS Standalone bagi Anggota Tim

> **Versi Bahasa:** Bahasa Indonesia | [English Version](../WINDOWS_INSTALLATION_GUIDE.md)

Panduan ini disusun sebagai petunjuk teknis bagi anggota tim untuk melakukan *setup* dan menjalankan **Model Bahaya Banjir 2D Provinsi Sumatera Barat** pada komputer bersistem operasi Windows (Windows 10 maupun Windows 11) tanpa memerlukan Git, Conda, maupun hak akses administrator.

---

## Alur Kerja Cepat 6 Langkah (Tanpa Git)

```mermaid
graph LR
    S1[1. Install VS Code] --> S2[2. Salin Folder Repo]
    S2 --> S3[3. Buka Folder di VS Code]
    S3 --> S4[4. Jalankan Setup Script]
    S4 --> S5[5. Pilih Kernel Notebook]
    S5 --> S6[6. Jalankan Cell Notebook]
```

### Langkah 1: Install Visual Studio Code
* Unduh dan *install* **Visual Studio Code (VS Code)** melalui situs resmi [https://code.visualstudio.com/](https://code.visualstudio.com/).
* Buka VS Code, pilih menu **Extensions** (`Ctrl + Shift + X`), lalu cari dan *install* dua ekstensi berikut:
  * **Python** (penerbit: Microsoft)
  * **Jupyter** (penerbit: Microsoft)

### Langkah 2: Salin Folder Proyek ke Komputer Lokal
* Salin folder `sumbar_flood_hazard` (melalui media penyimpanan eksternal, jaringan lokal, atau file `.zip`) ke *drive* lokal komputer Anda.
* Contoh lokasi penyimpanan yang disarankan: `D:\Project\sumbar_flood_hazard` atau `C:\Project\sumbar_flood_hazard`.
* Hindari meletakkan folder proyek di dalam folder yang tersinkronisasi otomatis seperti OneDrive untuk mencegah penguncian file GeoPackage dan file log saat simulasi berlangsung.

### Langkah 3: Buka Folder Proyek di VS Code
* Pada jendela VS Code, klik **File** -> **Open Folder...** -> pilih folder `D:\Project\sumbar_flood_hazard`.

### Langkah 4: Jalankan Automated Setup Script pada Terminal VS Code
* Buka terminal bawaan di VS Code (`Ctrl + ` ` ` atau klik **Terminal** -> **New Terminal**).
* Salin dan jalankan satu perintah berikut:
  ```powershell
  powershell -ExecutionPolicy Bypass -File .\env\setup_env.ps1
  ```
  *(Script ini secara otomatis memasang package manager `uv`, menyiapkan **Python 3.12** terisolasi, memasang seluruh geospatial package dalam waktu kurang dari 60 detik, membuka blokir binary file pada Windows 11, serta mendaftarkan Jupyter kernel).*

### Langkah 5: Buka Notebook dan Pilih Kernel yang Tepat
* Buka file master notebook pada [`notebook/master/01_sfincs_flood_hazard_run.ipynb`](../../notebook/master/01_sfincs_flood_hazard_run.ipynb).
* Pada sudut kanan atas editor notebook, klik tombol **Select Kernel**:
  * Pilih **Python Environments...** -> pilih **`.venv`** (`.\.venv\Scripts\python.exe`).
  * *(Atau pilih **Jupyter Kernel...** -> **`HydroMT-SFINCS`**).*

> [!IMPORTANT]
> **Pencegahan error "No module named pyproj":** Saat VS Code membuka notebook untuk pertama kali, sistem sering kali memilih instalasi Python global pada Windows secara *default*. Pastikan tombol *kernel* di sudut kanan atas selalu menampilkan **`.venv`** atau **`HydroMT-SFINCS`** sebelum menjalankan *cell* apa pun.

### Langkah 6: Atur Klaster DAS Tugas Anda dan Jalankan Simulasi
* Pada **Cell 1 (Control Panel Konfigurasi Pengguna)**, tentukan kode klaster DAS dan kala ulang (*return period*) yang ditugaskan kepada Anda:
  ```python
  SELECTED_CLUSTERS = ["DAS_104"]  # Ubah sesuai kode DAS tugas Anda (contoh: DAS_101 hingga DAS_114)
  SELECTED_RPS = ["rp100"]         # Pilihan: "rp2", "rp5", "rp10", "rp25", "rp50", "rp100"
  ```
* Jalankan **Cell 2 (Verifikasi Environment dan Data)** untuk memastikan *path* PROJ/GDAL terhubung dengan benar dan modul `sfincs_standalone_pipeline` termuat sempurna.
* Jalankan *cell* berikutnya secara berurutan atau klik **Run All**.

---

## Spesifikasi Stack dan Dependency

*Pipeline* ini distandardisasi pada **Python 3.12** yang dikelola menggunakan **`astral-sh/uv`** agar *virtual environment* bersifat konsisten, cepat, dan ringan tanpa ketergantungan Conda:

| Kategori | Komponen / Library | Spesifikasi Versi | Fungsi dalam Pipeline |
| :--- | :--- | :--- | :--- |
| **Runtime** | Python | `3.12.x` (64-bit) | *Core execution runtime* |
| **Package Manager** | `uv` | Versi terbaru | Pengelola *virtual environment* `.venv` dan *wheel* |
| **Hydrodynamic Engine** | SFINCS Native Binary | `2.4.0-galibier-release` | *Solver* aliran permukaan 2D dan *subgrid* |
| **Model Builder** | `hydromt` | `==0.10.1` | *Core framework* HydroMT |
| **Model Plugin** | `hydromt-sfincs` | `==1.2.2` | Pembangkit *grid* dan tabel *subgrid* SFINCS |
| **Vector Engine** | `geopandas` | `>=1.0.0` (1.1.x) | Pengolahan batas DAS, sungai, dan administrasi |
| **Raster Engine** | `rasterio` | `>=1.4.0` (1.5.x) | I/O GeoTIFF dan *downscaling* |
| **Projections / CRS** | `pyproj` | `>=3.7.0` (3.7.x) | Transformasi koordinat PROJ secara dinamis |
| **Data Array Engine** | `xarray` / `rioxarray` | `>=2024.1.0` / `>=0.18.0` | Pembacaan NetCDF hujan rancangan dan *geospatial cube* |
| **Unstructured Mesh** | `xugrid` | `>=0.14.0` | Operasi *spatial mesh* HydroMT |
| **Flow Routing** | `pyflwdir` | `>=0.5.10` | Ekstraksi jaringan sungai dan *flow direction* |
| **Visualisasi** | `matplotlib` / `folium` | `>=3.9.0` / `>=0.17.0` | Peta verifikasi 3 panel dan peta web interaktif |
| **Animasi** | `pillow` / `imageio` | `>=10.0.0` | Penyusunan animasi GIF perambatan banjir |

---

## Manual Setup (PowerShell Langkah demi Langkah)

Apabila Anda memilih menjalankan perintah instalasi secara manual tanpa menggunakan `setup_env.ps1`:

```powershell
# 1. Install package manager astral-sh/uv
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Perbarui variabel PATH pada sesi terminal aktif
$env:Path += ";$HOME\.local\bin;$HOME\.cargo\bin"

# 2. Bentuk virtual environment terpadu (.venv) dari pyproject.toml dan uv.lock
uv sync --extra dev

# 3. Daftarkan Jupyter Kernel untuk VS Code
.\.venv\Scripts\python.exe -m ipykernel install --user --name hydromt-sfincs --display-name "HydroMT-SFINCS"
```

---

## Verifikasi Native SFINCS Solver dan Library DLL

Pastikan *native binary* hidrodinamika SFINCS 64-bit dapat dijalankan dengan baik melalui PowerShell:

```powershell
.\bin\sfincs.exe
```

**Output yang Diharapkan:**
```text
 ******************************************************************************
 *                                                                            *
 * SFINCS: Super-Fast INundation of CoastS and riverS                         *
 *                                                                            *
 * Deltares, The Netherlands                                                  *
 * Version 2.4.0-galibier-release                                             *
 ******************************************************************************
```
*(Apabila banner di atas muncul, seluruh library pendukung Intel Fortran, OpenMP, HDF5, dan NetCDF di dalam folder `bin/` telah berfungsi penuh).*

---

## Urutan Eksekusi Cell pada Master Notebook

Saat menjalankan [`notebook/master/01_sfincs_flood_hazard_run.ipynb`](../../notebook/master/01_sfincs_flood_hazard_run.ipynb), jalankan seluruh *cell* secara berurutan:

* **Cell 1 (Control Panel Konfigurasi Pengguna):** Menentukan klaster DAS sasaran dan kala ulang (misalnya `SELECTED_CLUSTERS = ["DAS_104"]`, `SELECTED_RPS = ["rp100"]`).
* **Cell 2 (Verifikasi Environment dan Data):** Menghubungkan *path* PROJ/GDAL secara dinamis dari *virtual environment* aktif serta memuat modul `sfincs_standalone_pipeline`.
* **Cell 3 / Tahap 1 (Build Base Grid SFINCS):** Membangun *computational domain* terbatasi DAS pada resolusi *default* **80 m** (atau opsi 40 m), membentuk tabel *subgrid* 10 m secara *on-the-fly* dari FABDEM 30 m asli, melakukan *river burning* dengan dukungan `rivers_ar.gpkg`, serta memetakan kekasaran permukaan Manning dari Penutup Lahan RBI BIG.
* **Cell 4 / Tahap 2 (Direct Rainfall Forcing, Infiltrasi CNB, dan Pasang Surut MHHW):** Menerapkan *design storm hyetograph* 24 jam (`rainfall_<rp>.nc`) beserta periode *recession* nol hujan dinamis (24 hingga 48 jam), menyuntikkan infiltrasi `CNB` USDA-NRCS (`smaxfile`, `sefffile`, `ksfile` dengan `initial_sat_frac=0.0`), serta menetapkan batas pasang surut pesisir MHHW `+0,80 m` pada DAS pesisir.
* **Cell 5 / Tahap 3 (Eksekusi SFINCS Hydrodynamic Simulation Engine):** Menjalankan *2D solver* dilengkapi *progress bar* interaktif (memilih otomatis `bin/sfincs.exe` atau *fallback* Docker).
* **Cell 6 / Tahap 4 (Strict Hydrostatic Post-Processing [Minimum 15 cm], Subgrid QA, dan Klasifikasi BNPB):** Melakukan *downscaling* elevasi muka air ke resolusi 10 m, menghapus seluruh *pixel* dengan kedalaman di bawah **ambang minimum `0,15 m` (`15 cm`)** pada raster *Depth*, *Flood Hazard Index*, dan *Classes*, menerapkan pemulihan tepi `bilinear edge-NaN` murni tanpa penambahan *freeboard* sintetis (`freeboard_m=0.0`, jarak `<= 80 m`, `bridge_radius=3`) serta ambang kebersihan 4 arah `30 m x 30 m` (`hole_mmu_ha=1.0`), menghitung kelas bahaya resmi **Peraturan Kepala BNPB Nomor 02 Tahun 2012** beserta *continuous FHI surrogate* (0 hingga 1), serta menjalankan audit QA hipsometri *subgrid* dan validasi survei QField.
* **Cell 7 / Tahap 5 (Visualisasi Peta Hasil dan QA/QC):** Menampilkan gambar verifikasi 3 panel siap publikasi (Peta Kedalaman Genangan 10 m, Indeks Bahaya Kontinu, dan Peta 3 Kelas Bahaya BNPB).
* **Cell 8 / Tahap 6 (Animasi Perambatan Gelombang Banjir):** Menyusun dinamika genangan per jam menjadi file animasi GIF (`DASXXX_RPYYY_Flood_Animation.gif`).

---

## Pemeriksaan File Output

Setelah notebook selesai dijalankan, seluruh *output* tersimpan secara terstruktur pada direktori `outputs/{das_id}/{rp}/`:

```text
outputs/DAS_104/rp100/
├── DAS104_RP100_Flood_Depth.tif          <- Kedalaman genangan maksimum hasil hydrostatic refinement (m)
├── DAS104_RP100_Flood_Depth_raw.tif      <- Kedalaman hasil downscaling mentah sebelum penyaringan (m)
├── DAS104_RP100_FloodHazard_Index.tif    <- Indeks Bahaya Banjir kontinu Fuzzy Large (0,0 hingga 1,0) + .qml
├── DAS104_RP100_FloodHazard_Classes.tif  <- Kelas Bahaya Perka BNPB No. 02/2012 (1: Rendah, 2: Sedang, 3: Tinggi) + .qml
├── qa_report.json                        <- Laporan QA otomatis (roughness, mask/boundary, peak timing, volume)
└── survey_validation.json                <- Hasil validasi terhadap titik observasi lapangan QField
```

Buka file GeoTIFF tersebut menggunakan perangkat lunak **QGIS** untuk meninjau sebaran genangan dan menyusun tata letak peta tematik kebencanaan.

---

## Troubleshooting dan FAQ

| Permasalahan | Penyebab | Solusi |
| :--- | :--- | :--- |
| **`No module named pyproj`** atau **`ModuleNotFoundError`** | Notebook VS Code terhubung ke Python global Windows, bukan *virtual environment* `.venv`. | Klik **Select Kernel** di sudut kanan atas -> **Python Environments...** -> pilih **`.venv`** (atau **Jupyter Kernel...** -> **`HydroMT-SFINCS`**). |
| **`Running scripts is disabled on this system`** | Kebijakan eksekusi *script* PowerShell pada Windows masih terbatas. | Jalankan perintah: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| **Kernel `HydroMT-SFINCS` tidak tampil di VS Code** | VS Code masih menyimpan *cache* daftar *kernel* lama. | Tekan `Ctrl + Shift + P` -> pilih `Developer: Reload Window`. |
| **`sfincs.exe exited with code 3221225781`** | Runtime Microsoft Visual C++ 2015 sampai 2022 atau library DLL Intel Fortran belum lengkap. | *Install* [vc_redist.x64.exe](https://aka.ms/vs/17/release/vc_redist.x64.exe) dan pastikan seluruh 9 file DLL tetap berada di folder `bin/`. |
| **`PermissionError: [WinError 5] Access is denied` pada `sfincs.exe`** | Fitur Windows 11 SmartScreen / *Mark-of-the-Web* memblokir *binary file* hasil salinan jaringan. | Jalankan di PowerShell: `Get-ChildItem -Path .\bin -Recurse \| Unblock-File` (atau jalankan ulang `.\env\setup_env.ps1`). |
| **`PermissionError: [WinError 32]` pada `hydromt.log`** | File log masih terkunci oleh sesi *kernel* Jupyter sebelumnya atau aplikasi lain. | Klik tombol **Restart** pada bilah atas notebook (atau tutup jendela QGIS/editor yang membuka folder model), lalu jalankan ulang mulai dari Cell 1. |
| **`ImportError: DLL load failed while importing _gdal`** | Konflik *path* library PROJ atau GDAL (sering terjadi apabila QGIS terpasang di PATH sistem). | Pastikan Anda menggunakan *kernel* `.venv` (`HydroMT-SFINCS`) dan telah menjalankan Cell 2 notebook. |
| **Memori (RAM) penuh saat build grid** | Proses *tiling* raster FABDEM beresolusi tinggi saat ekstraksi *subgrid* 10 m. | Pastikan tersedia minimal 8 GB RAM bebas; tutup *browser* atau aplikasi latar belakang yang tidak diperlukan. |
