# Spesifikasi Teknis Pipeline Pemodelan Bahaya Banjir 2D HydroMT-SFINCS Standalone

## Pemodelan Hidrodinamika 2D Direct Rainfall-on-Grid untuk 17 Klaster DAS Provinsi Sumatera Barat

> **Versi Bahasa:** Bahasa Indonesia | [English Version](../PIPELINE.md)

Dokumen ini disusun mengacu pada dokumentasi resmi Deltares serta literatur ilmiah yang telah melalui penelaahan sejawat (*peer-reviewed*):
- Plugin HydroMT-SFINCS: https://deltares.github.io/hydromt_sfincs/latest/
- Dokumentasi Model SFINCS: https://sfincs.readthedocs.io/en/latest/
- HydroMT Core: https://deltares.github.io/hydromt/latest/
- Formulasi dan Validasi Global SFINCS: Leijnse et al. (2021); Eilander et al. (2023); Sadana et al. (2026)

---

## 1. Ringkasan Eksekutif dan Strategi Pemodelan

Repositori ini mengimplementasikan **Pipeline Pemodelan Bahaya Banjir Hidrodinamika 2D Standalone** berbasis **Deltares SFINCS** (*Super-Fast INundation of CoastS*, versi 2.4.0 *Galibier Release*) melalui **HydroMT `0.10.1`** dan **`hydromt-sfincs 1.2.2`** pada seluruh **17 klaster Daerah Aliran Sungai (DAS)** (`DAS_101` sampai dengan `DAS_114`, termasuk Kepulauan Mentawai `DAS_108_A` hingga `DAS_108_D`) di Provinsi Sumatera Barat, Indonesia.

### Prinsip Inti Pemodelan (Standar Nasional Kabupaten/Kota v2.0)

1. **Deteksi Zona UTM Otomatis dan Portabilitas Nasional:**
   Sistem mendeteksi zona proyeksi WGS 84 UTM secara otomatis untuk seluruh wilayah Indonesia (`EPSG:32646` hingga `EPSG:32654` untuk belahan bumi utara dan `EPSG:32746` hingga `EPSG:32754` untuk belahan bumi selatan melalui `scripts/geo_utils.py`), serta menstandardisasi parameterisasi penutup lahan RBI BIG menggunakan tabel kanonik nasional 15 kelas (`lookup_tables/national_rbi_lookup.csv`).
2. **Direct Rainfall-on-Grid dengan Dynamic Recession (Aliran Pluvial dan Fluvial Terpadu):**
   SFINCS menerapkan *design storm hyetograph* 24 jam secara langsung pada seluruh *active computational cell*, dilengkapi tambahan jam *recession* tanpa hujan yang skalanya disesuaikan secara dinamis menurut luas DAS (`24 jam` untuk luas `< 500 km²`, `36 jam` untuk `500 sampai 1.500 km²`, dan `48 jam` untuk `> 1.500 km²`), opsi *Areal Reduction Factor* (ARF USWB/WMO dengan *default* `apply_arf=False`), serta penyetelan numerik stabil (`alpha=0.65`, `huthresh=0.02`, `viscosity=0`).
3. **Active Watershed Masking, Pasang Surut MHHW Pesisir, dan Outflow Boundary:**
   *Active cell* dibatasi secara ketat pada poligon DAS hidrologis (`mask: das_region`, `reset_mask: true`) sehingga wilayah laut terbuka dan DAS tetangga tetap tidak aktif (`msk=0`), mengurangi jumlah *active cell* sebesar 40% hingga 70%. *Coastal waterlevel cell* (`msk=2`, $z \le 0$) diberi tinggi muka air pasang tertinggi rata-rata (**MHHW `+0,80 m`**) melalui file `sfincs.bnd` dan `sfincs.bzs`, sedangkan DAS daratan diberi *outflow boundary* (`msk=3`) pada titik keluaran sungai berelevasi terendah.
4. **Topografi Subgrid, On-the-Fly DEM Chipping, dan River Burning (Asumsi Awal Pra-Survei):**
   Secara *default* menggunakan **flux grid 80 m dan subgrid 10 m** (`configs/sfincs_standalone_build_80m_fast.yml`, `nr_subgrid_pixels: 8`, sekitar 13 kali lebih cepat), serta menyediakan opsi resolusi tinggi **40 m / 10 m** (`configs/sfincs_standalone_build.yml`, `nr_subgrid_pixels: 4`). *DEM chip* per DAS diekstraksi dan di-*reproject* secara bilinear *on-the-fly* melalui GDAL `WarpedVRT` dari **FABDEM 30 m asli** (`data_raw/fabdem/FABDEM30m_Sumbar.tif`). *Centerline* sungai diperkaya poligon lebar sungai RBI BIG (`data/rivers_ar.gpkg`) dengan *Manning roughness* saluran vegetatif ($n = 0,045$, Chow, 1959; Triatmodjo, 2008) dan geometri *fallback* pra-survei ($w = 8/15/22\text{ m}$, $d = 0,35/0,55/0,80\text{ m}$, dapat diganti data pengukuran penampang melintang BWS).
5. **Infiltrasi USDA-NRCS Curve Number Modern (`CNB`, Tanpa Double-Counting AMC):**
   Menggunakan skema *Curve Number with Recovery* SFINCS `v2.4.0+` (`smaxfile`, `sefffile`, `ksfile` dalam satuan meter) yang disintesis dari **Hydrologic Soil Group (HSG) Kementerian Pertanian x Penutup Lahan RBI BIG** (`scripts/generate_cn_raster.py`, kondisi `AMC-II` untuk `RP2` hingga `RP10` dan `AMC-III` via `cn2_to_cn3` untuk `RP25` hingga `RP100` dengan `initial_sat_frac=0.0`, `seff = S_max`, sehingga tidak terjadi *double-counting* kejenuhan tanah sesuai **USDA-NRCS NEH Part 630**, **SNI 2415:2016**, dan implementasi resmi Deltares SFINCS). Skema lama `scsfile` secara tegas dihindari karena cacat *zero-runoff* pada SFINCS `v2.4.0`, sedangkan raster infiltrasi konstan (`data/soil_infiltration_100m.tif`) dipertahankan sebagai *fallback* eksplisit.
6. **Strict Hydrostatic Post-Processing (Ambang Minimum 15 cm), Audit Volume Subgrid, dan Standar BNPB:**
   Elevasi muka air ($z_s$) di-*downscale* secara bilinear ke topografi *subgrid* 10 m, lalu seluruh *pixel* dengan kedalaman di bawah **`MIN_FLOOD_DEPTH_M = 0,15 m` (`15 cm`)** dihapus secara ketat dari raster *Depth*, *Flood Hazard Index*, dan *Classes* (Wing et al., 2018; Sampson et al., 2015; Bates et al., 2021). Tepian `bilinear edge-NaN` dipulihkan secara murni tanpa penambahan *freeboard* sintetis (`freeboard_m = 0,0 m`, `max_ext_dist_m = 80,0 m = 1,0 x dx`; Neal et al., 2012; Schumann et al., 2014). Koridor sungai RBI dilindungi saat penyaringan *hillslope noise* ($\ge 8^\circ$, Van Zuidam, 1985), diikuti *morphological bridging* jalan/tanggul (`bridge_radius = 3` / `30 m`), pembersihan *speck* dan *pinhole* terhubung 4 arah berukuran **`30 m x 30 m` (`0,09 ha`, setara 1 *pixel* asli FABDEM)**, batas rongga tergenang hidrostatis `1,0 ha` (`2 mm x 2 mm` skala 1:50.000; $\sigma = 1,0\text{ pixel}$; **SNI 6502.3:2010** dan **Peraturan BIG Nomor 18 Tahun 2021**), verifikasi *volume balance* melalui **kurva penyimpanan hipsometri *subgrid*** (`sfincs_subgrid.nc`), klasifikasi bahaya resmi **Peraturan Kepala BNPB Nomor 02 Tahun 2012**, *continuous FHI surrogate* (*Fuzzy Large*), serta validasi data survei lapangan QField.

---

## 2. Formulasi Teoretis dan Persamaan Pengatur

SFINCS menyelesaikan persamaan air dangkal dua dimensi terintegrasi kedalaman yang disederhanakan (pendekatan inersia lokal dan gelombang difusif) yang dipadukan dengan integrasi elevasi-volume serta kekasaran *subgrid* (Leijnse et al., 2021; Volp et al., 2013).

### 2.1 Persamaan Kontinuitas (Kekekalan Massa)
$$\frac{\partial \eta}{\partial t} + \frac{\partial (h u)}{\partial x} + \frac{\partial (h v)}{\partial y} = P - q_{\text{inf}}$$

Keterangan:
* $\eta(x, y, t)$: Elevasi muka air di atas datum (m).
* $h(x, y, t) = \eta - z_b$: Kedalaman air lokal (m), dengan $z_b$ adalah elevasi dasar tanah.
* $u, v$: Kecepatan aliran rata-rata kedalaman pada arah $x$ dan $y$ (m/detik).
* $P(x, y, t)$: Intensitas hujan langsung dari *design storm hyetograph* 24 jam (m/detik).
* $q_{\text{inf}}(x, y)$: Laju infiltrasi tanah terdistribusi secara spasial (m/detik).

### 2.2 Keseimbangan Momentum (Gesekan Permukaan dan Gravitasi)
Pada formulasi air dangkal *subgrid* yang disederhanakan (dengan inersia lokal dikendalikan oleh parameter `alpha` dan gesekan dasar diatur oleh koefisien *Manning roughness* $n$ terdistribusi):
$$u = \frac{R^{2/3}}{n \sqrt{|\nabla \eta|}} \left(-\frac{\partial \eta}{\partial x}\right), \qquad v = \frac{R^{2/3}}{n \sqrt{|\nabla \eta|}} \left(-\frac{\partial \eta}{\partial y}\right)$$

Keterangan: $R$ adalah jari-jari hidraulis *subgrid* dan $n$ adalah koefisien kekasaran permukaan Manning yang dipetakan dari Penutup Lahan RBI BIG (`lookup_tables/manning_lookup.csv`).

---

## 3. Parameterisasi Fisik Infiltrasi Tanah

### 3.1 Standar Utama v2.0: USDA-NRCS Curve Number with Recovery (`CNB`)
Secara *default* (`infiltration_mode="cnb"`), *pipeline* v2.0 menggunakan skema SFINCS `v2.4.0+` **Curve Number with Recovery (`smaxfile`, `sefffile`, `ksfile`)** dalam satuan meter yang dibangkitkan oleh `scripts/generate_cn_raster.py` dari persilangan **Tekstur Tanah Kementerian Pertanian (HSG A hingga D) x Penutup Lahan RBI BIG Kanonik (`lookup_tables/national_rbi_lookup.csv`)**:
* **Retensi Kelembapan Tanah Maksimum:** $S_{\max} = \left(\frac{1000}{\text{CN}} - 10\right) \times 0,0254\text{ m}$
* **Kondisi Kelembapan Awal Berdasarkan Kala Ulang (Tunggal Tanpa Double-Counting sesuai USDA-NRCS NEH Part 630 dan SNI 2415:2016):**
  - Hujan kala ulang sering (`RP2` hingga `RP10`): `data/cn_amc2_100m.tif` (`AMC-II` kondisi normal, `initial_sat_frac = 0.0` sehingga `seff = S_max(AMC-II)`)
  - Hujan monsun ekstrem (`RP25` hingga `RP100`): `data/cn_amc3_100m.tif` (`AMC-III` kondisi jenuh melalui `cn2_to_cn3`, `initial_sat_frac = 0.0` sehingga `seff = S_max(AMC-III)` tanpa *double-counting*)
* **Pengaman Kritis Solver:** File lama `scsfile` (`cna`) secara tegas dilarang dan dihapus dari `sfincs.inp` karena `SFINCS v2.4.0 Galibier` memiliki cacat *zero-runoff* saat memadukan `scsfile` dengan `netamprfile`.

### 3.2 Opsi Fallback: Matriks Constant-Loss Pra-Jenuh AMC-III (`qinf`)
Apabila `infiltration_mode="qinf"` dipilih (atau raster CN belum tersedia), sistem beralih ke matriks infiltrasi konstan AMC-III terkalibrasi (`lookup_tables/soil_infiltration_lookup.csv`, `amc_scale=1.0` tanpa penskalaan ganda) yang merepresentasikan tanah jenuh musim hujan (USDA-NRCS, 2004; Arsyad, 2010; Triatmodjo, 2008):

| Tekstur Tanah Kementan | Sawah | Permukiman | Tegalan / Ladang | Perkebunan | Hutan | Semak Belukar | Default |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Halus (Liat)** | `0.025` | `0.005` | `0.090` | `0.110` | `0.225` | `0.130` | `0.090` |
| **Agak Halus (Lempung Berliat)** | `0.025` | `0.005` | `0.170` | `0.150` | `0.340` | `0.190` | `0.150` |
| **Sedang (Lempung)** | `0.025` | `0.005` | `0.280` | `0.225` | `0.550` | `0.300` | `0.260` |
| **Agak Kasar (Lempung Berpasir)** | `0.025` | `0.005` | `0.450` | `0.375` | `0.825` | `0.525` | `0.450` |
| **Kasar (Pasir)** | `0.025` | `0.005` | `0.750` | `0.550` | `1.300` | `0.825` | `0.750` |
| **Gambut** | `0.025` | `0.005` | `0.075` | `0.090` | `0.110` | `0.090` | `0.075 hingga 0.110` |
| **Badan Air** | `0.000` | `0.000` | `0.000` | `0.000` | `0.000` | `0.000` | `0.000` |

*(Satuan: $\text{mm/jam}$. Catatan: Untuk pengembangan masa depan v3.0 menuju **HydroMT-SFINCS v2.0+ / SFINCS v2.5.0 Hautacam**, peta `CNB` ini dapat dimigrasikan secara langsung ke format NetCDF `inffile` dengan `inftype = cnb` beserta Quadtree adaptive refinement).*

---

## 4. Arsitektur Pipeline Menyeluruh

```mermaid
graph TD
    subgraph Tahap0["Tahap 0: Data Preparation (Auto-UTM)"]
        D1["FABDEM 30 m Asli (WGS 84)"] --> P0["notebook/master/00_data_preparation.ipynb"]
        D2["Tekstur Tanah Kementan GPKG"] --> P0
        D3["Penutup Lahan dan Sungai RBI BIG"] --> P0
        D4["NetCDF Hujan Rancangan (RP2 hingga RP100)"] --> P0
        P0 --> C1["data/cn_amc2_100m.tif dan cn_amc3_100m.tif"]
        P0 --> C2["data/landcover_rbi.tif (30 m)"]
        P0 --> C3["data/rivers.gpkg dan rivers_ar.gpkg"]
    end

    subgraph Tahap1to5["Tahap 1 hingga 5: Eksekusi SFINCS Standalone (Standar Nasional v2.0)"]
        C1 & C2 & C3 --> S1["Tahap 1: WarpedVRT Chip + Base Model + River Burning"]
        S1 --> M1["models_sfincs_standalone/DAS_XXX"]
        M1 --> S2["Tahap 2: Hujan 24 Jam + Auto-Recession + CNB + MHHW (+0,80 m)"]
        S2 --> M2["models_sfincs_standalone/DAS_XXX_rpYY"]
        M2 --> S3["Tahap 3: Native SFINCS Engine (bin/sfincs.exe)"]
        S3 --> O1["sfincs_map.nc"]
        O1 --> S4["Tahap 4: Bilinear Downscaling, Ambang 15 cm, 4-Arah 30x30 m, dan BNPB"]
        S4 --> R1["outputs/DAS_XXX/rpYY/DASXXX_RPYY_Flood_Depth.tif"]
        S4 --> R2["outputs/DAS_XXX/rpYY/DASXXX_RPYY_FloodHazard_Classes.tif"]
        S4 --> R3["outputs/DAS_XXX/rpYY/DASXXX_RPYY_FloodHazard_Index.tif"]
        S4 --> QA1["outputs/DAS_XXX/rpYY/qa_report.json (Subgrid Hypsometry)"]
        S4 --> QA2["outputs/DAS_XXX/rpYY/survey_validation.json"]
    end
```

---

## 5. Standar Klasifikasi Bahaya Banjir BNPB dan Post-Processing

Klasifikasi bahaya banjir mengacu pada **Peraturan Kepala BNPB Nomor 02 Tahun 2012 tentang Pedoman Umum Pengkajian Risiko Bencana**:

### 5.1 Matriks Ambang Kedalaman Genangan
* **Minimum Flood Hazard Depth (`MIN_FLOOD_DEPTH_M` / `hmin`):** $0,15\text{ m}$ (`15 cm`; *pixel* dengan kedalaman `< 0,15 m` dihapus menjadi `NaN` / Kelas `0` pada raster *Depth*, *Flood Hazard Index*, dan *Classes* guna menyaring *sheet-flow noise* serta *DEM pixel noise*; Wing et al., 2018; Sampson et al., 2015; Bates et al., 2021)
* **Rendah (Kelas 1):** $0,15\text{ m} \le h < 0,76\text{ m}$ (Hijau `#34A853`)
* **Sedang (Kelas 2):** $0,76\text{ m} \le h \le 1,50\text{ m}$ (Kuning `#FBBC05`)
* **Tinggi (Kelas 3):** $h > 1,50\text{ m}$ (Merah `#EA4335`)

### 5.2 Continuous Flood Hazard Index Surrogate (*Fuzzy Large Membership*)
Sebagai pelengkap kelas diskrit baku Peraturan Kepala BNPB Nomor 02 Tahun 2012 (`0,333`, `0,667`, dan `1,000`), sistem turut menghasilkan *continuous surrogate* berbasis fungsi keanggotaan *Fuzzy Large* (Klir dan Yuan, 1995) yang dikalibrasikan terhadap ambang kedalaman 0,76 m dan 1,50 m (`NaN` untuk $h < 0,15\text{ m}$):
$$\text{FHI}(h) = \frac{1}{1 + \left(\frac{h}{x_0}\right)^{-s}}, \quad x_0 = 1,125\text{ m},\; s = 1,75$$

### 5.3 Strict Hydrostatic Post-Processing (Ambang 15 cm), Boundary Anti-Aliasing, dan 4-Connected `30 m x 30 m` Floor
Untuk menghilangkan artefak diskritisasi *grid* dan tepian `bilinear edge-NaN` **tanpa menambahkan volume air sintetis**, modul *post-processing* v2.0 menjalankan 6 tahapan penyaringan hidrostatis ketat:
1. **Ambang Kedalaman Minimum 15 cm dan Penyaringan Hillslope Noise dengan Perlindungan Sungai RBI:** Menghapus secara ketat seluruh *pixel* dengan kedalaman `< 0,15 m` (`15 cm`; Wing et al., 2018; Sampson et al., 2015; Bates et al., 2021) serta menyaring *hillslope sheet-flow noise* terisolasi pada lereng curam ($\ge 8^\circ$, Van Zuidam, 1985) sambil **selalu melindungi koridor sungai RBI BIG** (*buffer* 30 m) agar alur banjir bandang pegunungan tetap terjaga.
2. **Pemulihan Tepi `Bilinear Edge-NaN` Murni (`freeboard_m = 0,0 m`, `max_ext_dist_m = 80,0 m`):** Mengekstrapolasikan permukaan muka air terhaluskan ($z_s$) ke arah luar maksimal `1,0 x dx` (`80 m` pada *grid* 80 m; `40 m` pada *grid* 40 m) semata-mata untuk memulihkan *pixel* `edge-NaN` bilinear yang elevasinya secara fisik berada di bawah muka air simulasi ($z_s - z_{\text{DEM}} \ge 0,15\text{ m}$; Neal et al., 2012; Schumann et al., 2014). Nilai *default* `freeboard_m` ditetapkan ketat sebesar **`0,0 m`** (tanpa penambahan *freeboard* buatan).
3. **Morphological Bridging dan Enclosed Hole-Filling:** *Disk kernel* (`bridge_radius=3`, radius 30 m sesuai lebar jalan/tanggul di Indonesia sebesar 10 hingga 30 m) menjembatani tanggul jalan sempit atau gorong-gorong dan mengisi rongga datar tertutup (`hole_mmu_ha=1.0`, setara keterbacaan `2 mm x 2 mm` pada skala 1:50.000; **SNI 6502.3:2010** dan **Peraturan BIG Nomor 18 Tahun 2021**) **hanya apabila tergenang secara hidrostatis** ($z_s - z_{\text{DEM}} \ge 0,15\text{ m}$, tanpa menaikkan kedalaman dangkal).
4. **Boundary Anti-Aliasing:** *Euclidean signed-distance transform* ($\sigma = 1,0\text{ pixel}$; Borgefors, 1986) menghilangkan tepian genangan bergerigi; setiap *pixel* yang nilainya turun di bawah `0,15 m` setelah penghalusan dihapus menjadi `NaN`.
5. **Pembersihan Speck dan Pinhole Terhubung 4 Arah `30 m x 30 m` (`0,09 ha`):** Menerapkan batas minimum setara **1 *pixel* asli sensor FABDEM (`0,09 ha`)** (`island_mmu_ha=0.09`, `min_hole_ha=0.09`; Hawker et al., 2022) menggunakan 4-connectivity (*rook*) untuk menghilangkan *pinhole* dan *speck* diagonal pada tampilan QGIS.
6. **Subgrid Hypsometric QA dan Validasi Survei:** Memverifikasi *volume balance* langsung dari `sfincs_subgrid.nc` (`z_level`, `z_volmax`) melalui `scripts/qa_checks.py` dan melakukan validasi terhadap titik observasi lapangan QField tersaring *outlier* (`hmin=0.15`, `max_valid_depth_m=8.0` pada `scripts/validate_against_survey.py`).

---

## 6. Python Execution Environment (`.venv` berbasis `uv`)

*Pipeline* berjalan pada satu Python 3.12 *virtual environment* terpadu yang dikelola oleh **`uv`**:

```powershell
uv sync --extra dev
.\.venv\Scripts\python.exe -m ipykernel install --user --name hydromt-sfincs --display-name "HydroMT-SFINCS"
.\.venv\Scripts\python.exe -m pytest
```

Seluruh *C-library* (`gdal`, `geos`, `proj`, `netcdf4`, `openmp`) telah dibundel secara lokal tanpa memerlukan Docker pada Windows.

---

## 7. Daftar Pustaka Ilmiah dan Peraturan Perundang-undangan

1. **Leijnse, T., van Ormondt, M., Nederhoff, K., & van Dongeren, A. (2021).** *Modeling compound flooding in coastal systems using a computationally efficient reduced-physics solver: Including fluvial, pluvial, tidal, wind- and wave-driven processes.* **Coastal Engineering**, 163, 103796. [https://doi.org/10.1016/j.coastaleng.2020.103796](https://doi.org/10.1016/j.coastaleng.2020.103796)
2. **Eilander, D., Boisgontier, H., Bouaziz, L. J. E., Buitink, J., Couasnon, A., Dalmijn, B., Hegnauer, M., de Jong, T., Loos, S., Marth, I., & van Verseveld, W. (2023).** *HydroMT: Automated and reproducible model building and analysis.* **Journal of Open Source Software**, 8(83), 4897. [https://doi.org/10.21105/joss.04897](https://doi.org/10.21105/joss.04897)
3. **Eilander, D., Couasnon, A., Leijnse, T., Ikeuchi, H., Yamazaki, D., Muis, S., Dullaart, J., Haag, A., Winsemius, H. C., & Ward, P. J. (2023).** *A globally applicable framework for compound flood hazard modeling.* **Natural Hazards and Earth System Sciences**, 23(2), 823 hingga 846. [https://doi.org/10.5194/nhess-23-823-2023](https://doi.org/10.5194/nhess-23-823-2023)
4. **Sadana, T., Aerts, J. C. J. H., Eilander, D., Merz, B., de Moel, H., Busker, T., Bril, V. C., & de Bruijn, J. (2026).** *Validation of the open-source hydrodynamic model SFINCS on historical river floods at the global scale.* **Hydrology and Earth System Sciences**, 30(17), 5491 hingga 5519. [https://doi.org/10.5194/hess-30-5491-2026](https://doi.org/10.5194/hess-30-5491-2026)
5. **Volp, N. D., van Prooijen, B. C., & Stelling, G. S. (2013).** *A finite volume approach for shallow water flow accounting for high-resolution bathymetry and roughness data.* **Water Resources Research**, 49(7), 4126 hingga 4135. [https://doi.org/10.1002/wrcr.20315](https://doi.org/10.1002/wrcr.20315)
6. **Hawker, L., Uhe, P., Paulo, L., Sosa, J., Savage, J., Sampson, C., & Neal, J. (2022).** *A 30m global map of elevation with forests and buildings removed.* **Environmental Research Letters**, 17(2), 024016. [https://doi.org/10.1088/1748-9326/ac4d4f](https://doi.org/10.1088/1748-9326/ac4d4f)
7. **USDA Natural Resources Conservation Service (2004).** *National Engineering Handbook (NEH), Part 630: Hydrology, Chapter 10.* USDA-NRCS, Washington, D.C.
8. **Arsyad, S. (2010).** *Konservasi Tanah dan Air* (Edisi Kedua). IPB Press, Bogor; dan **Triatmodjo, B. (2008).** *Hidrologi Terapan.* Beta Offset, Yogyakarta.
9. **Chow, V. T. (1959).** *Open-Channel Hydraulics.* McGraw-Hill, New York; dan **Arcement, G. J., & Schneider, V. R. (1989).** *Guide for Selecting Manning's Roughness Coefficients for Natural Channels and Flood Plains.* USGS Water-Supply Paper 2339. [https://doi.org/10.3133/wsp2339](https://doi.org/10.3133/wsp2339)
10. **Soille, P. (2003).** *Morphological Image Analysis: Principles and Applications* (2nd ed.). Springer. [https://doi.org/10.1007/978-3-662-05088-0](https://doi.org/10.1007/978-3-662-05088-0); dan **Borgefors, G. (1986).** *Distance transformations in digital images.* CVGIP, 34(3), 344 hingga 371. [https://doi.org/10.1016/S0734-189X(86)80047-0](https://doi.org/10.1016/S0734-189X(86)80047-0)
11. **Klir, G. J., & Yuan, B. (1995).** *Fuzzy Sets and Fuzzy Logic: Theory and Applications.* Prentice Hall, Upper Saddle River, NJ (*continuous FHI surrogate* *Fuzzy Large* terkalibrasi terhadap ambang Perka BNPB).
12. **Wing, O. E. J., et al. (2018).** *Estimates of present and future flood risk in the conterminous United States.* **Environmental Research Letters**, 13(3), 034023; **Sampson, C. C., et al. (2015).** **Water Resources Research**, 51(9), 7358 hingga 7381; **Bates, P. D., et al. (2021).** **Water Resources Research**, 57(2), e2020WR028673 (ambang minimum bahaya banjir `0,15 m` / `15 cm`).
13. **Neal, J., Schumann, G., & Bates, P. (2012).** **Water Resources Research**, 48(11), W11506; **Schumann, G. J.-P., et al. (2014).** **Journal of Hydrology**, 508, 289 hingga 298; **Van Zuidam, R. A. (1985).** *Aerial Photo-Interpretation in Terrain Analysis and Geomorphologic Mapping* (batas lereng perbukitan `>= 8 derajat`).
14. **Peraturan Kepala BNPB Nomor 02 Tahun 2012** (*Pedoman Umum Pengkajian Risiko Bencana*), **Permen PUPR Nomor 12/PRT/M/2014** (*Penyelenggaraan Sistem Drainase Perkotaan*), **SNI 2415:2016** (*Tata Cara Perhitungan Debit Banjir Rencana*), **SNI 2830:2008**, **SNI 6502.3:2010** (*Peta Rupabumi Skala 1:50.000*), **Peraturan BIG Nomor 18 Tahun 2021** (*Tata Cara Penyelenggaraan Informasi Geospasial*), dan **Pushidrosal TNI AL / BIG SRGI** (*Daftar Pasang Surut Teluk Bayur, Padang*).
