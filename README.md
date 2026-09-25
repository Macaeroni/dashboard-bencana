# dashboard-bencana
Dashboard untuk melihat sebaran bencana yang terjadi sesuai dengan data yang diberikan
Website Dashboard : https://dashboard-bencana-gfm.streamlit.app/
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
