# Spesifikasi dan Persyaratan Data Hidraulika Balai Wilayah Sungai (BWS)

## Pedoman Baku Integrasi Data Infrastruktur Sungai dan Pos Duga Air ke dalam HydroMT-SFINCS

> **Versi Bahasa:** Bahasa Indonesia | [English Version](../BWS_DATA_SPECIFICATIONS.md)

**Model Sasaran:** HydroMT-SFINCS Mandiri (Standar Nasional Indonesia v2.0)  
**Sistem Referensi Koordinat (CRS) Sasaran:** Auto-UTM Indonesia (`EPSG:32646` hingga `EPSG:32754`, contoh: `EPSG:32747` untuk Provinsi Sumatera Barat) atau `EPSG:4326` (WGS 84)  
**Lokasi Penyimpanan Baku:** `data_raw/bws/`

---

## 1. Gambaran Umum dan Struktur Penyimpanan Data

Untuk meningkatkan ketelitian model bahaya banjir dasar menjadi model hidraulika yang merepresentasikan infrastruktur pengendali banjir serta pengamatan lapangan secara akurat, tiga lapisan data opsional berikut dapat dihimpun dari **Balai Wilayah Sungai (BWS) Sumatera V**:

```text
data_raw/bws/
│
├── tanggul_sungai.gpkg       <- 1. Bangunan Pengendali Banjir / Tanggul Sungai (Thin Dikes)
├── pos_awlr.gpkg             <- 2. Pos Duga Air Otomatis (AWLR) sebagai Titik Pengamatan
└── debit_inflow.csv          <- 3. Hidrograf Debit Masuk Hulu / Pelepasan Bendungan
```

---

## 2. Spesifikasi dan Persyaratan Format Dataset

### Dataset 1: Tanggul Pengendali Banjir dan Tebing Sungai (`BWS_LEVEES_GPKG`)
* **Sumber Data Lazim:** Inventarisasi Infrastruktur Sungai BWS (Data Tanggul dan Pengaman Tebing Sungai).
* **Jalur Berkas yang Diharapkan:** `data_raw/bws/tanggul_sungai.gpkg` (atau format `.shp`).
* **Tipe Geometri:** `LineString` atau `MultiLineString` (mengikuti alur tanggul di sepanjang bantaran sungai atau dinding penahan banjir).
* **Metode Pemasukan SFINCS:** `sf.setup_structures(structures="...", stype="weir", par1=0.6)`
* **Fungsi Fisik:** Menahan atau membatasi limpasan air ke dataran banjir hingga elevasi muka air melampaui elevasi puncak tanggul ($z_{\text{crest}}$).

#### Persyaratan Tabel Atribut
| Nama Kolom | Tipe Data | Sifat | Satuan | Keterangan dan Contoh |
| :--- | :--- | :--- | :--- | :--- |
| `name` atau `nama` | `String` | Opsional | - | Nama tanggul (contoh: `Tanggul Batang Anai Kiri`) |
| `z_crest` atau `elev` | `Float` | **Wajib** | $\text{m}$ (MSL) | Elevasi puncak tanggul di atas permukaan laut rata-rata (MSL). |
| `par1` | `Float` | Opsional | - | Koefisien peluapan bendung (*weir discharge coefficient*, nilai baku: `0.6`) |
| `stype` | `String` | Opsional | - | Jenis bangunan: `"weir"`, `"gate"`, atau `"dam"` (nilai baku: `"weir"`) |

> [!IMPORTANT]
> - **Datum Elevasi:** Pastikan nilai `z_crest` mengacu pada datum vertikal yang sama dengan FABDEM (EGM2008 / MSL dalam satuan meter), bukan tinggi relatif terhadap tanah di sekitarnya.
> - **Kualitas Geometri:** Garis vektor tidak boleh memiliki segmen bernilai panjang nol atau simpul koordinat bertumpuk.

---

### Dataset 2: Pos Duga Air Otomatis / AWLR (`BWS_GAUGES_GPKG`)
* **Sumber Data Lazim:** Stasiun Hidrometeorologi BWS (Pos Duga Air / AWLR / ARR).
* **Jalur Berkas yang Diharapkan:** `data_raw/bws/pos_awlr.gpkg` (atau format `.shp`).
* **Tipe Geometri:** `Point` (lokasi stasiun atau sensor telemetri).
* **Metode Pemasukan SFINCS:** `sf.setup_observation_points(locations="...")`
* **Fungsi Fisik:** SFINCS merekam hidrograf keluaran berfrekuensi tinggi (elevasi muka air $z_s(t)$ dan kedalaman $h(t)$) pada koordinat tersebut guna kalibrasi langsung terhadap kejadian banjir historis.

#### Persyaratan Tabel Atribut
| Nama Kolom | Tipe Data | Sifat | Satuan | Keterangan dan Contoh |
| :--- | :--- | :--- | :--- | :--- |
| `name` atau `pos_id` | `String` | **Wajib** | - | Identitas unik atau nama pos (contoh: `AWLR_Btg_Kuranji_Padang`) |
| `sungai` | `String` | Opsional | - | Nama sungai tempat stasiun berada (contoh: `Batang Kuranji`) |
| `x` / `y` | `Float` | Turunan | $\text{m}$ atau derajat | Koordinat spasial titik yang terletak tepat di dalam alur sungai. |

> [!TIP]
> **Peringatan Penempatan Titik:** Pastikan geometri titik diletakkan tepat di dalam sel kisi alur sungai utama. Apabila titik AWLR terletak pada tanah tinggi yang kering di tepi sungai, SFINCS akan menghasilkan kedalaman air sebesar 0 m.

---

### Dataset 3: Hidrograf Debit Terukur Hulu / Debit Masuk (`BWS_INFLOW_HYDROGRAPHS`)
* **Sumber Data Lazim:** Catatan hidrograf per jam dari bendungan hulu, bendung, atau pengukuran debit pada pintu air.
* **Jalur Berkas yang Diharapkan:** `data_raw/bws/debit_inflow.csv` disertai berkas titik koordinat pasangannya `data_raw/bws/pos_inflow.gpkg`.
* **Tipe Geometri:** Tabel deret waktu (`.csv`) yang terhubung ke lokasi titik (`Point`).
* **Metode Pemasukan SFINCS:** `sf.setup_discharge_forcing_from_points(locations="...", timeseries="...")`
* **Fungsi Fisik:** Memasukkan volume aliran air berubah waktu ($Q$ dalam satuan $\text{m}^3/\text{detik}$) ke hulu sungai atau hilir waduk.

#### Persyaratan Format Tabel (`debit_inflow.csv`)
* **Baris 1:** Judul kolom yang sama persis dengan nilai pada kolom `name` di lapisan titik pos debit masuk.
* **Kolom 1:** Indeks waktu dalam format baku ISO (`YYYY-MM-DD HH:MM:SS`).
* **Kolom Lainnya:** Nilai debit aliran sungai dalam satuan meter kubik per detik ($\text{m}^3/\text{detik}$).

#### Contoh Struktur Berkas CSV
```csv
time,INFLOW_BATANG_ANAI,INFLOW_BATANG_KURANJI
2026-08-25 00:00:00,45.2,12.8
2026-08-25 01:00:00,88.5,24.3
2026-08-25 02:00:00,165.0,75.4
2026-08-25 03:00:00,240.2,110.0
2026-08-25 04:00:00,180.5,85.2
2026-08-25 05:00:00,95.0,35.1
```

---

## 3. Daftar Periksa Kendali Mutu (QA/QC) saat Menerima Data dari BWS

Sebelum memasukkan jalur berkas ke dalam [`notebook/master/01_sfincs_flood_hazard_run.ipynb`](../../notebook/master/01_sfincs_flood_hazard_run.ipynb), lakukan pemeriksaan berikut:

1. [ ] **Pemeriksaan Sistem Koordinat (CRS):** Seluruh lapisan vektor telah diproyeksikan ke `EPSG:32747` (UTM Zona 47S) atau zona UTM sesuai wilayah studi.
2. [ ] **Elevasi Puncak Tanggul:** Pastikan nilai `z_crest` lebih tinggi dari elevasi tanah DEM sekitarnya (sebagai contoh, apabila elevasi tanah 12 m, maka nilai `z_crest` seharusnya sekitar 14 m, bukan nilai relatif +2 m).
3. [ ] **Ketepatan Lokasi Titik:** Verifikasi pada perangkat lunak QGIS bahwa seluruh titik AWLR menempel tepat pada garis sungai `rivers.gpkg`.
4. [ ] **Kesesuaian Cap Waktu CSV:** Rentang waktu pada berkas CSV selaras dengan waktu mulai dan durasi kejadian hujan yang disimulasikan.
