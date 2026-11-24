# Indeks Dokumentasi Teknis Pipeline Pemodelan Bahaya Banjir Sumatera Barat

> **Versi Bahasa:** Bahasa Indonesia (Standar Pedoman Teknis Pemerintahan) | [English Documentation](../README.md)

Selamat datang di pusat dokumentasi teknis **Pipeline Pemodelan Bahaya Banjir Hidrodinamika 2D Standalone Provinsi Sumatera Barat** yang menggunakan perangkat lunak **Deltares SFINCS** (*Super-Fast INundation of CoastS*, versi 2.4.0 *Galibier Release*) dan **HydroMT-SFINCS `1.2.2`** pada Python *virtual environment* terpadu (`.venv` berbasis `uv`).

Direktori ini memuat panduan instalasi, petunjuk teknis pelaksanaan, spesifikasi data, serta referensi formulasi ilmiah untuk **17 klaster Daerah Aliran Sungai (DAS)** (`DAS_101` sampai dengan `DAS_114`, termasuk Kepulauan Mentawai yang dipisahkan menjadi `DAS_108_A` hingga `DAS_108_D`) di Provinsi Sumatera Barat untuk 6 skenario kala ulang (*return period*: `RP2`, `RP5`, `RP10`, `RP25`, `RP50`, dan `RP100`).

---

## Daftar Dokumen dan Navigasi

| Dokumen | Sasaran Pengguna | Ruang Lingkup dan Isi |
| :--- | :--- | :--- |
| [**`PANDUAN_INSTALASI_WINDOWS.md`**](PANDUAN_INSTALASI_WINDOWS.md) | Pemula, Anggota Tim Teknis, Analis GIS | **Panduan instalasi 6 langkah pada Windows** untuk menyiapkan *virtual environment* `.venv` (`uv sync --extra dev`), mendaftarkan *kernel* Jupyter `HydroMT-SFINCS`, membuka blokir *binary file* pada Windows 11, serta menjalankan simulasi tanpa Conda. |
| [**`TUTORIAL.md`**](TUTORIAL.md) | Geospatial Modeler, Hidrolog | **Petunjuk teknis pelaksanaan langkah demi langkah** mencakup verifikasi *input dataset*, simulasi *prototype* satu klaster DAS (mode *default* 80 m atau opsi 40 m), *batch processing*, pengujian QA/QC, serta pembersihan *cache* dan file sementara. |
| [**`PIPELINE.md`**](PIPELINE.md) | Peneliti, Ahli Hidraulika, Penelaah Teknis | **Referensi formulasi matematis dan arsitektur hidrodinamika**: persamaan air dangkal, *active domain masking* DAS, hipsometri *subgrid* 10 m, infiltrasi tanah USDA-NRCS `CNB`, *strict hydrostatic post-processing* (ambang 15 cm), serta klasifikasi bahaya banjir sesuai Peraturan Kepala BNPB Nomor 02 Tahun 2012. |
| [**`SPESIFIKASI_DATA_BWS.md`**](SPESIFIKASI_DATA_BWS.md) | BWS Sumatera V, Kementerian PUPR, Surveyor Lapangan | **Spesifikasi dan persyaratan baku data BWS** yang mengatur format geometri dan skema atribut untuk integrasi tanggul sungai (`tanggul_sungai.gpkg`), pos duga air otomatis (`pos_awlr.gpkg`), dan hidrograf debit masuk (`debit_inflow.csv`). |
| [**`REMEDIATION_REPORT.md`**](../REMEDIATION_REPORT.md) | Auditor Teknis, Senior Modeler | **Catatan audit rekayasa (arsip berbahasa Inggris)** yang mendokumentasikan riwayat perbaikan fisika, numerik, dan geospasial beserta bukti *unit test*. |

---

## Ringkasan Metodologi: Standar Nasional Kabupaten/Kota v2.0

* **Hydrodynamic Engine:** *Native Windows 64-bit binary* SFINCS versi 2.4.0 *Galibier Release* (`bin/sfincs.exe`) dengan parameter numerik stabil (`alpha=0.65`, `huthresh=0.02`, `viscosity=0`) serta deteksi zona proyeksi **Auto-UTM Indonesia** secara otomatis (`EPSG:32646` hingga `EPSG:32754`).
* **Diskritisasi Spasial (*Grid* dan *Subgrid*):** *Computational domain* dibatasi secara ketat pada poligon DAS aktif (`mask: das_region`, nilai `msk=0` di luar DAS) dengan konfigurasi *default* **flux grid 80 m dan subgrid 10 m** (`configs/sfincs_standalone_build_80m_fast.yml`, sekitar 13 kali lebih cepat) atau opsi resolusi tinggi **40 m / 10 m** (`configs/sfincs_standalone_build.yml`). *DEM chip* diekstraksi dan di-*reproject* secara *on-the-fly* melalui GDAL `WarpedVRT` dari FABDEM 30 m asli.
* **Direct Rainfall Forcing dan Pasang Surut Pesisir:** *Design storm hyetograph* 24 jam dilengkapi periode *recession* tanpa hujan secara dinamis berdasarkan luas DAS (`24`, `36`, atau `48` jam) serta tinggi muka air pasang tertinggi rata-rata pesisir Sumatera Barat (**MHHW `+0,80 m`**, mengacu data pasut Teluk Bayur/Padang Pushidrosal dan BIG SRGI; wajib disesuaikan di luar Sumatera Barat) melalui file `sfincs.bnd` dan `sfincs.bzs`.
* **Infiltrasi Tanah (`CNB`):** Menggunakan metode *USDA-NRCS Curve Number with Recovery* (`smaxfile`, `sefffile`, `ksfile` dalam satuan meter) yang disintesis dari persilangan data Tekstur Tanah Kementerian Pertanian (HSG A hingga D) dan Penutup Lahan RBI BIG (`AMC-II` untuk `RP2` hingga `RP10`, serta `AMC-III` via `cn2_to_cn3` untuk `RP25` hingga `RP100` dengan `initial_sat_frac=0.0` tanpa *double-counting* kejenuhan tanah sesuai **USDA-NRCS NEH Part 630** dan **SNI 2415:2016**), dengan *fallback* laju infiltrasi konstan `qinf`.
* **River Burning (Asumsi Awal Pra-Survei):** *Centerline* sungai diperkaya poligon lebar sungai RBI BIG (`data/rivers_ar.gpkg`) dengan kekasaran Manning `n = 0,045` (Chow, 1959; Triatmodjo, 2008) dan geometri *fallback* pra-survei (lebar 8, 15, dan 22 m; kedalaman 0,35, 0,55, dan 0,80 m yang dapat diganti data pengukuran penampang melintang BWS).
* **Strict Hydrostatic Post-Processing (Ambang Minimum 15 cm), Subgrid QA, dan Standar BNPB:** *Bilinear downscaling* muka air ke resolusi 10 m dengan **minimum flood hazard depth `0,15 m` (`15 cm`)** yang diterapkan ketat pada raster *Depth*, *Flood Hazard Index*, dan *Classes* (Wing et al., 2018; Sampson et al., 2015; Bates et al., 2021), pemulihan tepi `bilinear edge-NaN` murni tanpa penambahan *freeboard* sintetis (`freeboard_m=0.0`, jarak `<= 80 m`), *morphological bridging* melintasi jalan/tanggul (`bridge_radius=3` / `30 m`), pembersihan *pinhole* dan *speck* terhubung 4 arah minimal `30 m x 30 m` (`0,09 ha`, setara 1 *pixel* asli FABDEM) serta rongga hidrostatis `<= 1,0 ha` (`2 mm x 2 mm` skala 1:50.000; $\sigma = 1,0\text{ pixel}$; **SNI 6502.3:2010** dan **Peraturan BIG Nomor 18 Tahun 2021**), verifikasi *volume balance* berbasis kurva hipsometri *subgrid*, klasifikasi bahaya banjir baku mengacu **Peraturan Kepala BNPB Nomor 02 Tahun 2012**, serta *continuous FHI surrogate* (*Fuzzy Large*).

---

Untuk memulai persiapan perangkat komputer pada sistem operasi Windows, silakan lanjutkan langsung ke [**`PANDUAN_INSTALASI_WINDOWS.md`**](PANDUAN_INSTALASI_WINDOWS.md).
