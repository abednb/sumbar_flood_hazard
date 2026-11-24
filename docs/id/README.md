# Indeks Dokumentasi Teknis Pemodelan Bahaya Banjir Sumatera Barat

> **Versi Bahasa:** Bahasa Indonesia (Standar Pedoman Teknis Pemerintahan) | [English Documentation](../README.md)

Selamat datang di pusat dokumentasi teknis **Alur Kerja Pemodelan Bahaya Banjir Hidrodinamika 2D Mandiri (*Standalone*) Provinsi Sumatera Barat** yang menggunakan perangkat lunak **Deltares SFINCS** (*Super-Fast INundation of CoastS*, versi 2.4.0 *Galibier Release*) dan **HydroMT-SFINCS `1.2.2`** pada lingkungan virtual Python terpadu (`.venv` berbasis `uv`).

Direktori ini memuat panduan instalasi, petunjuk teknis pelaksanaan, spesifikasi data, serta referensi formulasi ilmiah untuk **17 klaster Daerah Aliran Sungai (DAS)** (`DAS_101` sampai dengan `DAS_114`, termasuk Kepulauan Mentawai yang dipisahkan menjadi `DAS_108_A` hingga `DAS_108_D`) di Provinsi Sumatera Barat untuk 6 skenario kala ulang (`RP2`, `RP5`, `RP10`, `RP25`, `RP50`, dan `RP100`).

---

## Daftar Dokumen dan Navigasi

| Dokumen | Sasaran Pengguna | Ruang Lingkup dan Isi |
| :--- | :--- | :--- |
| [**`PANDUAN_INSTALASI_WINDOWS.md`**](PANDUAN_INSTALASI_WINDOWS.md) | Pemula, Anggota Tim Teknis, Analis SIG | **Panduan instalasi 6 langkah pada Windows** untuk menyiapkan lingkungan virtual `.venv` (`uv sync --extra dev`), mendaftarkan kernel Jupyter `HydroMT-SFINCS`, membuka blokir berkas biner pada Windows 11, serta menjalankan simulasi tanpa Conda. |
| [**`TUTORIAL.md`**](TUTORIAL.md) | Pemodel Geospasial, Hidrolog | **Petunjuk teknis pelaksanaan langkah demi langkah** mencakup pemeriksaan data siap pakai, uji coba satu klaster DAS (mode standar 80 m atau opsi 40 m), pemrosesan massal, pengujian kendali mutu (QA/QC), serta pembersihan berkas sementara. |
| [**`PIPELINE.md`**](PIPELINE.md) | Peneliti, Ahli Hidraulika, Penelaah Teknis | **Referensi formulasi matematis dan arsitektur hidrodinamika**: persamaan air dangkal, pembatasan domain aktif DAS, hipsometri subkisi 10 m, infiltrasi tanah USDA-NRCS `CNB`, pengolahan pascasimulasi Opsi B, serta klasifikasi bahaya banjir sesuai Peraturan Kepala BNPB Nomor 02 Tahun 2012. |
| [**`SPESIFIKASI_DATA_BWS.md`**](SPESIFIKASI_DATA_BWS.md) | BWS Sumatera V, Kementerian PUPR, Surveyor Lapangan | **Spesifikasi dan persyaratan baku data BWS** yang mengatur format geometri dan tabel atribut untuk integrasi tanggul sungai (`tanggul_sungai.gpkg`), pos duga air otomatis (`pos_awlr.gpkg`), dan hidrograf debit masuk (`debit_inflow.csv`). |
| [**`REMEDIATION_REPORT.md`**](../REMEDIATION_REPORT.md) | Auditor Teknis, Pemodel Senior | **Catatan audit rekayasa (arsip berbahasa Inggris)** yang mendokumentasikan riwayat perbaikan fisika, numerik, dan geospasial beserta bukti pengujian unit. |

---

## Ringkasan Metodologi: Standar Nasional Kabupaten/Kota v2.0

* **Mesin Hidrodinamika:** Berkas biner asli Windows 64-bit SFINCS versi 2.4.0 *Galibier Release* (`bin/sfincs.exe`) dengan pengaturan numerik stabil (`alpha=0.65`, `huthresh=0.02`, `viscosity=0`) serta deteksi zona proyeksi **Auto-UTM Indonesia** secara otomatis (`EPSG:32646` hingga `EPSG:32754`).
* **Diskritisasi Spasial:** Domain komputasi dibatasi secara ketat pada poligon DAS aktif (`mask: das_region`, nilai `msk=0` di luar DAS) dengan konfigurasi baku **kisi fluks 80 m dan subkisi 10 m** (`configs/sfincs_standalone_build_80m_fast.yml`, sekitar 13 kali lebih cepat) atau opsi resolusi tinggi **40 m / 10 m** (`configs/sfincs_standalone_build.yml`). Data elevasi dipotong secara langsung (*on-the-fly*) melalui `WarpedVRT` dari FABDEM 30 m asli.
* **Pemaksaan Hujan Langsung dan Pasang Surut Pesisir:** Hujan rancangan 24 jam dilengkapi tambahan periode resesi tanpa hujan secara dinamis berdasarkan luas DAS (`24`, `36`, atau `48` jam) serta tinggi muka air pasang tertinggi rata-rata pesisir Sumatera Barat (**MHHW `+0,80 m`**, mengacu data pasut Teluk Bayur/Padang Pushidrosal dan BIG SRGI; wajib disesuaikan di luar Sumatera Barat) melalui berkas `sfincs.bnd` dan `sfincs.bzs`.
* **Infiltrasi Tanah (`CNB`):** Menggunakan metode *USDA-NRCS Curve Number with Recovery* (`smaxfile`, `sefffile`, `ksfile` dalam satuan meter) yang disintesis dari persilangan data Tekstur Tanah Kementerian Pertanian (Kelompok Tanah Hidrologi A hingga D) dan Penutup Lahan RBI BIG (`AMC-II` untuk `RP2` hingga `RP10`, serta `AMC-III` via `cn2_to_cn3` untuk `RP25` hingga `RP100` dengan `initial_sat_frac=0.0` tanpa penghitungan ganda kejenuhan tanah sesuai **USDA-NRCS NEH Part 630** dan **SNI 2415:2016**), dengan cadangan laju infiltrasi konstan `qinf`.
* **Representasi Alur Sungai (Asumsi Awal Pra-Survei):** Garis tengah sungai diperkaya poligon lebar sungai RBI BIG (`data/rivers_ar.gpkg`) dengan kekasaran Manning `n = 0,045` (Chow, 1959; Triatmodjo, 2008) dan geometri cadangan pra-survei (lebar 8, 15, dan 22 m; kedalaman 0,35, 0,55, dan 0,80 m yang dapat diganti data pengukuran penampang melintang BWS).
* **Pengolahan Pascasimulasi Hidrostatis Ketat (Ambang Minimum 15 cm), Kendali Mutu Subkisi, dan Standar BNPB:** Penurunan skala (*downscaling*) muka air secara bilinear ke resolusi 10 m dengan **batas minimum kedalaman bahaya banjir `0,15 m` (`15 cm`)** yang diterapkan ketat pada raster Kedalaman, Indeks Bahaya, dan Kelas Bahaya (Wing et al., 2018; Sampson et al., 2015; Bates et al., 2021), pemulihan tepi `bilinear edge-NaN` murni tanpa penambahan tinggi air sintetis (`freeboard_m=0.0`, jarak `<= 80 m`), penjembatanan jalan/tanggul (`bridge_radius=3` / `30 m`), pembersihan lubang dan bercak terhubung 4 arah minimal `30 m x 30 m` (`0,09 ha`, setara 1 piksel asli FABDEM) serta rongga hidrostatis `<= 1,0 ha` (`2 mm x 2 mm` skala 1:50.000; $\sigma = 1,0\text{ piksel}$; **SNI 6502.3:2010** dan **Peraturan BIG Nomor 18 Tahun 2021**), verifikasi neraca volume berbasis kurva hipsometri subkisi, klasifikasi bahaya banjir baku mengacu **Peraturan Kepala BNPB Nomor 02 Tahun 2012**, serta surogat Indeks Bahaya Banjir kontinu (*Fuzzy Large*).

---

Untuk memulai persiapan perangkat komputer pada sistem operasi Windows, silakan lanjutkan langsung ke [**`PANDUAN_INSTALASI_WINDOWS.md`**](PANDUAN_INSTALASI_WINDOWS.md).
