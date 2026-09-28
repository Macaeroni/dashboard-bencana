# dashboard-bencana
Dashboard untuk melihat sebaran bencana yang terjadi sesuai dengan data yang diberikan
Website Dashboard : https://dashboard-bencana-gfm.streamlit.app/

Dashboard Pemantauan Bencana — Kabupaten Bogor
================================================
Prototipe dashboard interaktif berbasis Streamlit, cakupan Kabupaten
Bogor (40 kecamatan), dengan data meteorologi per kecamatan yang
dikorelasikan terhadap kejadian bencana, indeks risiko, dan indikator
meteorologi.

Cara menjalankan:
    pip install streamlit pandas numpy plotly
    streamlit run dashboard_bencana.py

FORMAT CSV YANG DIDUKUNG
-------------------------
1. Format asli laporan BPBD Kabupaten Bogor (terdeteksi otomatis),
   dengan ciri: ada baris judul di atas, lalu header berisi kolom
   seperti KECAMATAN, TANGGAL KEJADIAN, LONGITUDE, LATITUDE, dan 8
   kolom jenis bencana terpisah (BANJIR, TANAH LONGSOR, KARHUTLA,
   ANGIN KENCANG, KEKERINGAN, GERAKAN TANAH, GEMPABUMI, NON ALAM)
   bernilai 1/kosong, plus kolom dampak (korban, rumah rusak, dst).
   Dashboard otomatis:
     - mendeteksi baris header (melewati baris judul bila ada)
     - mengubah 8 kolom jenis bencana jadi satu kolom `jenis_bencana`
     - mem-parse kolom LONGITUDE/LATITUDE yang formatnya bercampur
       (derajat-menit-detik, desimal, dengan/tanpa simbol N/S/E/W,
       dengan/tanpa tanda kutip) menjadi koordinat desimal
     - kalau koordinat kosong/tidak terbaca, otomatis diisi dari titik
       tengah kecamatan (lihat isi_koordinat_otomatis())
     - menghitung `keparahan` (indeks 1-5) dan `rumah_terdampak` dari
       kolom korban jiwa & rumah rusak/terancam/terendam
2. Format sederhana (skema lama): tanggal, jenis_bencana, kecamatan,
   [lat, lon opsional], [meninggal, mengungsi, rumah_terdampak,
   keparahan, status opsional].
Jika CSV yang diunggah tidak cocok dengan kedua format di atas, atau
tidak ada file yang diunggah, dashboard memakai DATA SIMULASI.

DATA METEOROLOGI:
    Data kejadian bencana DAN data meteorologi masing-masing bisa
    dimasukkan lewat sidebar dengan dua cara: unggah file CSV (boleh
    beberapa file sekaligus) atau baca semua CSV dari sebuah folder
    (folder di komputer yang menjalankan dashboard). Kolom wajib
    meteorologi: kecamatan, curah hujan; opsional: suhu, kelembaban,
    kecepatan angin. Kecamatan yang tidak ada di data otomatis
    dilengkapi dari data simulasi (lihat load_meteo_data()). Tanpa
    sumber apa pun, seluruhnya simulasi.

CATATAN PENTING:
    - Koordinat 40 kecamatan (KECAMATAN_BOGOR) adalah APROKSIMASI
      kasar, dipakai untuk fallback saja — bukan sentroid resmi.
    - Kolom kerugian dalam rupiah tidak tersedia di data BPBD, sehingga
      dashboard memakai `rumah_terdampak` (rumah rusak+terancam+
      terendam) sebagai proksi dampak.
    - `keparahan` untuk data BPBD dihitung dari kombinasi korban jiwa
      dan rumah terdampak — bukan angka resmi, hanya proksi untuk
      keperluan visualisasi/pengurutan.
    - Indeks risiko pada dashboard ini adalah komposit sederhana hasil
      simulasi (lihat compute_risk_index()), BUKAN IRBI resmi BNPB
      (yang levelnya per kabupaten/kota, bukan per kecamatan).

Struktur file:
    1. Konfigurasi halaman & gaya (CSS)
    2. Data referensi 40 kecamatan Kabupaten Bogor
    3. Parser koordinat & pembangkit data simulasi
    4. Pemuatan data: deteksi format BPBD / format sederhana / simulasi
       + pemuatan data meteorologi (CSV opsional / simulasi)
    5. Sidebar: filter kecamatan, jenis bencana, tahun, bulan
    5.5 Bar logo (kanan atas, sejajar tab) & peta analisis 2026
    6. Baris KPI ringkasan
    7. Peta sebaran titik kejadian
    8. Tren bulanan per jenis bencana
    9. Korelasi intensitas meteorologi vs kejadian bencana (+ indeks risiko)
    10. Indikator meteorologi per kecamatan
    11. Komposisi jenis bencana & ranking kecamatan
    12. Tabel log kejadian terbaru
==========================================================================================================================================
FOLDER PETA ANALISIS
==========================================================================================================================================
Folder peta_analisis untuk peta hasil analisis bencana tahun 2026 (per jenis bencana),
yang ditampilkan di tab "Peta Analisis Bencana 2026" pada dashboard.
 
Taruh file peta di folder ini (sejajar dengan dashboard_bencana.py),
dengan pola nama:
 
    peta_<jenis_bencana>_2026.<ekstensi>
 
Nama file yang harus dipakai untuk tiap jenis bencana:
 
    peta_banjir_2026.png              (atau .jpg / .jpeg / .html)
    peta_tanah_longsor_2026.png
    peta_kebakaran_2026.png
    peta_kekeringan_2026.png
    peta_angin_kencang_2026.png
    peta_karhutla_2026.png
 
Format yang didukung:
  - .png / .jpg / .jpeg  -> untuk peta berupa gambar statis
    (hasil ekspor dari QGIS, ArcGIS, atau software GIS lainnya)
  - .html                -> untuk peta interaktif
    (hasil ekspor dari Folium, Kepler.gl, atau library peta interaktif lain)
 
Kalau file untuk satu jenis bencana belum ada, dashboard akan menampilkan
pesan peringatan (bukan error) yang memberi tahu nama file apa yang masih
dicari, jadi tab ini tetap aman dibuka meski belum semua peta lengkap.
==========================================================================================================================================
FOLDER LOGOS
==========================================================================================================================================
Folder logos untuk logo institusi yang ditampilkan di bagian atas sidebar
dashboard (Dashboard Utama), berurutan dari kiri: IPB University,
BPBD Kabupaten Bogor, BMKG.

Taruh file logo di folder ini (sejajar dengan dashboard_bencana.py),
dengan nama file PERSIS seperti berikut (boleh .png / .jpg / .jpeg):

    logo_ipb.png      -> logo IPB University
    logo_bpbd.png      -> logo BPBD Kabupaten Bogor
    logo_bmkg.png      -> logo BMKG

Kalau salah satu file belum ada, slot logo itu otomatis dilewati
(dashboard tetap jalan normal, tidak error) dan hanya menampilkan
nama institusinya sebagai teks kecil.

Saran: pakai logo dengan latar belakang transparan (PNG) berukuran
persegi atau mendekati persegi, supaya rapi saat ditampilkan
berdampingan dalam 3 kolom kecil di sidebar.
