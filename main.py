Folder ini untuk peta hasil analisis bencana tahun 2026 (multi-bencana, per bulan),
yang ditampilkan di tab "Peta Analisis 2026" pada dashboard. Setiap peta memuat
SEMUA jenis bencana, dan ada satu peta untuk tiap bulan Januari sampai Agustus.

Taruh file peta di folder ini (sejajar dengan main.py), dengan pola nama:

    peta_multi_bencana_<bulan>_2026.<ekstensi>

Nama file yang harus dipakai untuk tiap bulan:

    peta_multi_bencana_januari_2026.png     (atau .jpg / .jpeg / .html)
    peta_multi_bencana_februari_2026.png
    peta_multi_bencana_maret_2026.png
    peta_multi_bencana_april_2026.png
    peta_multi_bencana_mei_2026.png
    peta_multi_bencana_juni_2026.png
    peta_multi_bencana_juli_2026.png
    peta_multi_bencana_agustus_2026.png

Format yang didukung:
  - .png / .jpg / .jpeg  -> untuk peta berupa gambar statis
    (hasil ekspor dari QGIS, ArcGIS, atau software GIS lainnya)
  - .html                -> untuk peta interaktif
    (hasil ekspor dari Folium, Kepler.gl, atau library peta interaktif lain)

Kalau file untuk satu bulan belum ada, dashboard akan menampilkan pesan
peringatan (bukan error) yang memberi tahu nama file apa yang masih dicari,
jadi tab ini tetap aman dibuka meski belum semua peta lengkap.
