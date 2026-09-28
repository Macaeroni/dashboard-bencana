import base64
import io
import re
import os
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

# ---------------------------------------------------------------------------
# 1. KONFIGURASI HALAMAN & GAYA
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Dashboard Bencana — Kabupaten Bogor",
    page_icon="🌧️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Jenis bencana mengikuti 8 kolom pada format BPBD Kabupaten Bogor.
TYPE_COLUMN_MAP = {
    "BANJIR": "Banjir",
    "TANAH LONGSOR": "Tanah Longsor",
    "KARHUTLA": "Karhutla",
    "ANGIN KENCANG": "Angin Kencang",
    "KEKERINGAN": "Kekeringan",
    "GERAKAN TANAH": "Gerakan Tanah",
    "GEMPABUMI": "Gempa Bumi",
    "NON ALAM": "Non Alam",
}
PALETTE = {
    "Banjir": "#3FA79E",
    "Tanah Longsor": "#D9A441",
    "Karhutla": "#E1863C",
    "Angin Kencang": "#8E8CD8",
    "Kekeringan": "#C49A6C",
    "Gerakan Tanah": "#A8763F",
    "Gempa Bumi": "#E8543F",
    "Non Alam": "#6B7A8F",
    "Tidak Diketahui": "#8A96A5",
}
# Dipakai untuk plot korelasi meteorologi: jenis yang berkaitan langsung
# dengan cuaca/iklim (bukan gempa, non-alam, dsb).
HIDROMETEOROLOGI = ["Banjir", "Tanah Longsor", "Angin Kencang", "Kekeringan"]

RISK_COLOR = {"Rendah": "#3FA79E", "Sedang": "#D9A441", "Tinggi": "#E8543F"}

CUSTOM_CSS = """
<style>
html, body, .stApp { font-family: 'IBM Plex Sans', sans-serif; }
button[data-baseweb="tab"] {
    white-space: nowrap !important;
    height: auto !important;
    min-height: 44px !important;
}
[data-baseweb="tab-list"] {
    overflow-x: auto !important;
    flex-wrap: nowrap !important;
    height: auto !important;
}
[data-baseweb="tab-highlight"] { height: 2.5px !important; }
.block-container {
    padding-top: 3.5rem; padding-bottom: 3rem; max-width: 1360px;
    padding-left: 3rem; padding-right: 3rem;
    position: relative;
}
/* Logo di ujung kanan, sejajar baris tab */
div[data-testid="stElementContainer"]:has(.logo-bar),
.element-container:has(.logo-bar) {
    position: absolute;
    top: 3.5rem;
    right: 3rem;
    height: 44px;
    width: auto;
    z-index: 5;
}
.logo-bar {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 14px;
    height: 44px;
}
.logo-bar img {
    height: 28px;
    width: auto;
    object-fit: contain;
}
div[data-testid="stMetric"] {
    background: rgba(127,127,127,0.06);
    border: 1px solid rgba(127,127,127,0.18);
    border-radius: 10px;
    padding: 12px 16px 8px;
}
div[data-testid="stMetricLabel"],
div[data-testid="stMetricLabel"] p,
div[data-testid="stMetricLabel"] div {
    font-size: 0.8rem;
    opacity: 0.75;
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: clip !important;
    line-height: 1.25;
}
h1, h2, h3 { font-family: 'IBM Plex Sans', sans-serif; font-weight: 600; }
.dash-caption { color: rgba(127,127,127,0.9); font-size: 0.85rem; margin-top: -8px; }
.proto-note {
    border: 1px dashed rgba(127,127,127,0.35);
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 0.85rem;
    opacity: 0.85;
    margin-bottom: 1rem;
}

/* Layar kecil (HP): logo di baris sendiri, tab turun di bawahnya */
@media (max-width: 768px) {
    .block-container {
        padding-left: 1rem;
        padding-right: 1rem;
    }
    div[data-testid="stElementContainer"]:has(.logo-bar),
    .element-container:has(.logo-bar) {
        right: 1rem;
        left: 1rem;
    }
    .logo-bar {
        justify-content: flex-end;
        gap: 10px;
    }
    .logo-bar img {
        height: 24px;
    }
    /* turunkan tab utama supaya tidak tertimpa logo */
    [data-testid="stTabs"] > [data-baseweb="tab-list"] {
        margin-top: 52px;
    }
    /* tab di dalam tab (mis. "Curah hujan per kecamatan") tidak ikut turun */
    [data-testid="stTabs"] [data-testid="stTabs"] > [data-baseweb="tab-list"] {
        margin-top: 0;
    }
}

</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 2. DATA REFERENSI 40 KECAMATAN KABUPATEN BOGOR
# ---------------------------------------------------------------------------
# Nama mengikuti UU No. 102 Tahun 2024 tentang Kabupaten Bogor (Pasal 3).
# Koordinat adalah APROKSIMASI titik tengah wilayah untuk kebutuhan
# fallback peta — ganti dengan data BIG/BPS untuk presisi lokasi.

KECAMATAN_BOGOR = [
    {"n": "Cibinong", "lat": -6.4817, "lon": 106.8540},
    {"n": "Gunung Putri", "lat": -6.4400, "lon": 106.9250},
    {"n": "Citeureup", "lat": -6.4850, "lon": 106.8850},
    {"n": "Sukaraja", "lat": -6.5600, "lon": 106.8300},
    {"n": "Babakan Madang", "lat": -6.5700, "lon": 106.8900},
    {"n": "Jonggol", "lat": -6.4550, "lon": 107.0450},
    {"n": "Cileungsi", "lat": -6.4100, "lon": 106.9700},
    {"n": "Cariu", "lat": -6.4300, "lon": 107.1500},
    {"n": "Sukamakmur", "lat": -6.5900, "lon": 107.0700},
    {"n": "Parung", "lat": -6.4050, "lon": 106.7350},
    {"n": "Gunung Sindur", "lat": -6.3600, "lon": 106.7100},
    {"n": "Kemang", "lat": -6.4900, "lon": 106.7350},
    {"n": "Bojonggede", "lat": -6.4600, "lon": 106.8100},
    {"n": "Leuwiliang", "lat": -6.5600, "lon": 106.6300},
    {"n": "Ciampea", "lat": -6.5600, "lon": 106.6900},
    {"n": "Cibungbulang", "lat": -6.5450, "lon": 106.6600},
    {"n": "Pamijahan", "lat": -6.6100, "lon": 106.6800},
    {"n": "Rumpin", "lat": -6.4550, "lon": 106.5900},
    {"n": "Jasinga", "lat": -6.5300, "lon": 106.4700},
    {"n": "Parung Panjang", "lat": -6.3800, "lon": 106.5200},
    {"n": "Nanggung", "lat": -6.6200, "lon": 106.5800},
    {"n": "Cigudeg", "lat": -6.5400, "lon": 106.4900},
    {"n": "Tenjo", "lat": -6.4400, "lon": 106.4700},
    {"n": "Ciawi", "lat": -6.6350, "lon": 106.8500},
    {"n": "Cisarua", "lat": -6.6900, "lon": 106.9500},
    {"n": "Megamendung", "lat": -6.6700, "lon": 106.9200},
    {"n": "Caringin", "lat": -6.6600, "lon": 106.8300},
    {"n": "Cijeruk", "lat": -6.6650, "lon": 106.8000},
    {"n": "Ciomas", "lat": -6.6100, "lon": 106.7700},
    {"n": "Dramaga", "lat": -6.5600, "lon": 106.7300},
    {"n": "Tamansari", "lat": -6.6250, "lon": 106.7500},
    {"n": "Klapanunggal", "lat": -6.4500, "lon": 106.9600},
    {"n": "Ciseeng", "lat": -6.4200, "lon": 106.6900},
    {"n": "Rancabungur", "lat": -6.5000, "lon": 106.7350},
    {"n": "Sukajaya", "lat": -6.6100, "lon": 106.5000},
    {"n": "Tanjungsari", "lat": -6.6350, "lon": 106.9100},
    {"n": "Tajurhalang", "lat": -6.4700, "lon": 106.7900},
    {"n": "Cigombong", "lat": -6.7150, "lon": 106.8200},
    {"n": "Leuwisadeng", "lat": -6.5750, "lon": 106.6100},
    {"n": "Tenjolaya", "lat": -6.6000, "lon": 106.7000},
]

MAP_CENTER = {"lat": -6.55, "lon": 106.80}
MAP_ZOOM = 9.4
# True  = tampilkan opsi "Pilih folder" (membaca folder di komputer yang
#         menjalankan dashboard; HANYA cocok kalau dijalankan lokal).
# False = hanya opsi unggah file CSV (untuk dashboard yang di-hosting online).
IZINKAN_PILIH_FOLDER_SERVER = False
LOGO_DIR = "logos"  # taruh logo_ipb.png, logo_bpbd.png, logo_bmkg.png di sini (tampil di kanan atas, sejajar tab)

# ---------------------------------------------------------------------------
# 3. PARSER KOORDINAT & PEMBANGKIT DATA SIMULASI
# ---------------------------------------------------------------------------


def parse_koordinat(value, tipe: str) -> float:
    """Mengubah nilai koordinat mentah (format campur: derajat-menit-detik
    dengan berbagai simbol, desimal dengan/tanpa simbol derajat,
    dengan/tanpa huruf mata angin N/S/E/W) menjadi derajat desimal.

    `tipe` harus "lat" atau "lon" — dipakai untuk menentukan tanda
    (+/-) default ketika huruf mata angin tidak ada, dan untuk
    memvalidasi hasil ada di rentang wajar Kabupaten Bogor. Nilai yang
    gagal di-parse atau di luar rentang wajar dikembalikan sebagai NaN
    (akan diisi otomatis dari koordinat kecamatan, lihat
    isi_koordinat_otomatis())."""
    if pd.isna(value):
        return np.nan
    s = str(value).strip()
    if s == "" or s.lower() == "nan":
        return np.nan

    # normalisasi tanda kutip pintar -> lurus
    s = s.replace("\u201c", '"').replace("\u201d", '"').replace("''", '"')

    hemisphere = None
    m_hem = re.search(r"([NSEWnsew])\s*$", s)
    if m_hem:
        hemisphere = m_hem.group(1).upper()
        s = s[: m_hem.start()].strip()
    # huruf mata angin hanya valid untuk sumbunya sendiri (N/S untuk lat,
    # E/W untuk lon) — kalau tertukar (kesalahan input), abaikan saja.
    valid_hem = {"N", "S"} if tipe == "lat" else {"E", "W"}
    if hemisphere not in valid_hem:
        hemisphere = None

    negative = s.strip().startswith("-")
    s_clean = s.lstrip("-").strip()

    decimal = None
    # pola derajat-menit-detik: 106°53'14,634 / 6⁰28'40 / dst.
    dms = re.match(r"^(\d{1,3})[°ºo⁰\s]+(\d{1,2})['\u2019\s]+([\d.,]+)", s_clean)
    if dms:
        deg = float(dms.group(1))
        minute = float(dms.group(2))
        sec_str = dms.group(3).replace(",", ".").strip(".")
        try:
            sec = float(sec_str) if sec_str else 0.0
        except ValueError:
            sec = 0.0
        if minute < 60 and sec < 60:
            decimal = deg + minute / 60 + sec / 3600
    if decimal is None:
        # pola desimal: 106.488465° / 6,587742
        dd = re.match(r"^(\d{1,3}[.,]\d+)", s_clean)
        if dd:
            decimal = float(dd.group(1).replace(",", "."))
        else:
            try:
                decimal = float(s_clean.replace(",", "."))
            except ValueError:
                return np.nan

    if hemisphere in ("S", "W"):
        decimal = -abs(decimal)
    elif hemisphere in ("N", "E"):
        decimal = abs(decimal)
    elif negative:
        decimal = -abs(decimal)
    else:
        decimal = -abs(decimal) if tipe == "lat" else abs(decimal)

    # validasi rentang longgar wilayah Kabupaten Bogor
    if tipe == "lat" and not (-8 <= decimal <= -5):
        return np.nan
    if tipe == "lon" and not (105 <= decimal <= 108):
        return np.nan
    return round(decimal, 6)


def isi_koordinat_otomatis(df_events: pd.DataFrame, rng_seed: int = 1) -> pd.DataFrame:
    """Mengisi lat/lon yang kosong/tidak valid dari titik tengah
    kecamatan (KECAMATAN_BOGOR), ditambah offset acak kecil supaya
    titik-titik di kecamatan yang sama tidak saling menumpuk di peta.
    Nama kecamatan yang tidak cocok dengan daftar 40 kecamatan akan
    diberi tahu lewat peringatan di sidebar dan tidak tampil di peta."""
    df_events = df_events.copy()
    rng = np.random.default_rng(rng_seed)
    lookup = {k["n"].lower(): (k["lat"], k["lon"]) for k in KECAMATAN_BOGOR}

    if "lat" not in df_events.columns:
        df_events["lat"] = np.nan
    if "lon" not in df_events.columns:
        df_events["lon"] = np.nan

    tidak_cocok = set()
    need_fill = df_events["lat"].isna() | df_events["lon"].isna()
    for i in df_events.index[need_fill]:
        key = str(df_events.at[i, "kecamatan"]).strip().lower()
        if key in lookup:
            base_lat, base_lon = lookup[key]
            df_events.at[i, "lat"] = base_lat + rng.uniform(-0.03, 0.03)
            df_events.at[i, "lon"] = base_lon + rng.uniform(-0.03, 0.03)
        else:
            tidak_cocok.add(df_events.at[i, "kecamatan"])

    if tidak_cocok:
        st.sidebar.warning(
            "Nama kecamatan berikut tidak cocok dengan daftar 40 kecamatan "
            "Kabupaten Bogor, sehingga tidak tampil di peta: "
            + ", ".join(sorted(str(x) for x in tidak_cocok))
        )
    return df_events


STATUS_OPTIONS = ["Siaga Darurat", "Tanggap Darurat", "Pemantauan", "Selesai"]


@st.cache_data
def generate_dummy_data(n_rows: int = 220, seed: int = 42) -> pd.DataFrame:
    """Data kejadian bencana simulasi, tersebar di 40 kecamatan Kabupaten
    Bogor, memakai skema kolom yang sama dengan hasil parsing CSV asli
    (lihat load_data())."""
    rng = np.random.default_rng(seed)
    types = list(TYPE_COLUMN_MAP.values())
    rows = []
    for _ in range(n_rows):
        jenis = rng.choice(types)
        kec = KECAMATAN_BOGOR[rng.integers(0, len(KECAMATAN_BOGOR))]
        bulan = rng.integers(1, 10)
        hari = rng.integers(1, 28)
        tahun = rng.choice([2024, 2025, 2026], p=[0.25, 0.35, 0.40])
        keparahan = round(float(rng.uniform(1.0, 5.0)), 1)
        rumah_terdampak = int(rng.poisson(keparahan * 15))
        rows.append(
            {
                "tanggal": pd.Timestamp(year=int(tahun), month=int(bulan), day=int(hari)),
                "jenis_bencana": jenis,
                "kecamatan": kec["n"],
                "lat": kec["lat"] + rng.uniform(-0.03, 0.03),
                "lon": kec["lon"] + rng.uniform(-0.03, 0.03),
                "meninggal": int(rng.poisson(keparahan * 0.3)),
                "mengungsi": int(rng.poisson(keparahan * 80)),
                "rumah_terdampak": rumah_terdampak,
                "keparahan": keparahan,
                "status": rng.choice(STATUS_OPTIONS, p=[0.40, 0.35, 0.15, 0.10]),
            }
        )
    return pd.DataFrame(rows).sort_values("tanggal", ascending=False).reset_index(drop=True)


@st.cache_data
def generate_meteo_data(seed: int = 7) -> pd.DataFrame:
    """Data meteorologi simulasi per kecamatan. Dipakai sebagai fallback
    penuh (tanpa CSV) maupun pelengkap kecamatan yang belum ada di CSV
    yang diunggah — lihat load_meteo_data()."""
    rng = np.random.default_rng(seed)
    rows = []
    for kec in KECAMATAN_BOGOR:
        southness = max(0.0, (-6.35 - kec["lat"]))
        base_hujan = 12 + southness * 55
        curah = max(0.0, float(rng.normal(base_hujan, 12)))
        rows.append(
            {
                "kecamatan": kec["n"],
                "lat": kec["lat"],
                "lon": kec["lon"],
                "curah_hujan_mm_hari": round(curah, 1),
                "kategori_intensitas": klasifikasi_curah_hujan(curah),
                "suhu_c": round(float(rng.normal(26 - southness * 4, 1.2)), 1),
                "kelembaban_persen": round(float(np.clip(rng.normal(80, 6), 55, 99)), 0),
                "kecepatan_angin_kmh": round(float(np.clip(rng.normal(14, 5), 2, 40)), 1),
            }
        )
    return pd.DataFrame(rows)


def klasifikasi_curah_hujan(mm_per_hari: float) -> str:
    """Klasifikasi intensitas hujan harian mengikuti kategori BMKG
    (mm/hari): ringan 5-20, sedang 20-50, lebat 50-100, sangat lebat >100."""
    if mm_per_hari < 5:
        return "Tidak Hujan/Berawan"
    elif mm_per_hari < 20:
        return "Ringan"
    elif mm_per_hari < 50:
        return "Sedang"
    elif mm_per_hari < 100:
        return "Lebat"
    else:
        return "Sangat Lebat"


# Alias nama kolom yang diterima untuk CSV data meteorologi, supaya tidak
# harus mengetik nama kolom persis seperti di kode (mis. "curah hujan" atau
# "Curah Hujan (mm/hari)" akan tetap dikenali sebagai `curah_hujan_mm_hari`).
ALIAS_KOLOM_METEO = {
    "kecamatan": {"kecamatan", "kec", "nama_kecamatan"},
    "curah_hujan_mm_hari": {
        "curah_hujan_mm_hari", "curah_hujan", "curah_hujan_mm", "curah_hujan_mmhari",
        "curahhujan", "hujan", "rainfall", "precipitation",
    },
    "suhu_c": {"suhu_c", "suhu", "temperature", "temp", "suhu_celcius", "suhu_udara"},
    "kelembaban_persen": {"kelembaban_persen", "kelembaban", "kelembapan", "humidity"},
    "kecepatan_angin_kmh": {
        "kecepatan_angin_kmh", "kecepatan_angin", "angin", "wind_speed", "windspeed", "kecepatan_angin_km_jam",
    },
}


def _normalisasi_nama_kolom(nama: str) -> str:
    """Menyeragamkan nama kolom supaya bisa dicocokkan ke ALIAS_KOLOM_METEO:
    huruf kecil, isi dalam kurung dibuang (mis. "(mm/hari)"), spasi/simbol
    diganti underscore. Contoh: "Curah Hujan (mm/hari)" -> "curah_hujan"."""
    s = str(nama).strip().lower()
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s


def _petakan_kolom_meteo(df_csv: pd.DataFrame) -> pd.DataFrame:
    """Mengganti nama kolom CSV meteorologi (apa pun variasi penulisannya)
    menjadi nama kolom baku yang dipakai kode, berdasarkan ALIAS_KOLOM_METEO."""
    kolom_ternormalisasi = {_normalisasi_nama_kolom(c): c for c in df_csv.columns}
    peta_ganti_nama = {}
    for nama_baku, alias_set in ALIAS_KOLOM_METEO.items():
        for alias in alias_set:
            if alias in kolom_ternormalisasi:
                peta_ganti_nama[kolom_ternormalisasi[alias]] = nama_baku
                break
    return df_csv.rename(columns=peta_ganti_nama)


KOLOM_METEO_FINAL = [
    "kecamatan", "lat", "lon", "curah_hujan_mm_hari", "kategori_intensitas",
    "suhu_c", "kelembaban_persen", "kecepatan_angin_kmh",
]


def load_meteo_data(sumber) -> pd.DataFrame:
    """Titik masuk data meteorologi per kecamatan.

    `sumber` adalah daftar (nama_file, file_like) hasil unggahan CSV
    (satu atau beberapa file) ATAU hasil pembacaan folder — lihat
    widget_sumber_data(). Semua file digabung jadi satu.

    Kolom WAJIB: `kecamatan`, `curah_hujan_mm_hari` (nama kolom fleksibel,
    lihat ALIAS_KOLOM_METEO). Kolom OPSIONAL: `suhu_c`, `kelembaban_persen`,
    `kecepatan_angin_kmh`. Kolom `kategori_intensitas` selalu dihitung
    ulang dari curah hujan, jadi tidak perlu diisi di CSV.

    Kalau satu kecamatan muncul di lebih dari satu baris (mis. banyak
    file harian/bulanan atau beberapa pos hujan di kecamatan yang sama),
    nilainya DIRATA-RATAKAN per kecamatan.

    Kecamatan yang tidak ada di data (dari 40 kecamatan Kabupaten Bogor)
    otomatis diisi dari data simulasi supaya peta & grafik tetap lengkap,
    dan diberi tahu lewat pesan di sidebar. Kalau tidak ada sumber, atau
    tidak ada file yang formatnya sesuai, seluruhnya memakai simulasi
    (generate_meteo_data())."""
    df_simulasi = generate_meteo_data()
    if not sumber:
        return df_simulasi

    kolom_angka = ["curah_hujan_mm_hari", "suhu_c", "kelembaban_persen", "kecepatan_angin_kmh"]
    nama_kanonik = {k["n"].lower(): k["n"] for k in KECAMATAN_BOGOR}
    koordinat = {k["n"]: (k["lat"], k["lon"]) for k in KECAMATAN_BOGOR}

    potongan = []
    for nama, f in sumber:
        try:
            f.seek(0)
            d = pd.read_csv(f)
        except Exception:
            st.sidebar.error(f"CSV meteorologi '{nama}' gagal dibaca, dilewati.")
            continue
        d.columns = [str(c).strip() for c in d.columns]
        d = _petakan_kolom_meteo(d)
        if not {"kecamatan", "curah_hujan_mm_hari"}.issubset(d.columns):
            st.sidebar.error(
                f"CSV meteorologi '{nama}' tidak punya kolom wajib `kecamatan` dan "
                "curah hujan (atau variasi penulisannya), dilewati."
            )
            continue
        potongan.append(d)

    if not potongan:
        st.sidebar.error("Tidak ada file meteorologi yang bisa dipakai. Memakai data simulasi.")
        return df_simulasi

    d = pd.concat(potongan, ignore_index=True)
    d["kecamatan"] = d["kecamatan"].astype(str).str.strip()
    for kol in kolom_angka:
        if kol not in d.columns:
            d[kol] = np.nan
        d[kol] = pd.to_numeric(d[kol], errors="coerce")
    d = d.dropna(subset=["curah_hujan_mm_hari"])

    kunci = d["kecamatan"].str.lower()
    tidak_dikenal = sorted(set(d.loc[~kunci.isin(nama_kanonik.keys()), "kecamatan"]))
    if tidak_dikenal:
        st.sidebar.warning(
            "Nama kecamatan berikut di data meteorologi tidak cocok dengan daftar "
            "40 kecamatan Kabupaten Bogor, sehingga diabaikan: " + ", ".join(tidak_dikenal)
        )
    d = d[kunci.isin(nama_kanonik.keys())].copy()
    if d.empty:
        st.sidebar.error("Tidak ada kecamatan yang cocok di data meteorologi. Memakai data simulasi.")
        return df_simulasi
    d["kecamatan"] = d["kecamatan"].str.lower().map(nama_kanonik)

    jumlah_baris = len(d)
    d = d.groupby("kecamatan", as_index=False)[kolom_angka].mean()
    if jumlah_baris > len(d):
        st.sidebar.info(
            f"{jumlah_baris} baris data meteorologi digabung menjadi {len(d)} kecamatan "
            "(nilai dirata-rata per kecamatan)."
        )
    d["curah_hujan_mm_hari"] = d["curah_hujan_mm_hari"].round(1)
    d["kategori_intensitas"] = d["curah_hujan_mm_hari"].apply(klasifikasi_curah_hujan)
    d["lat"] = d["kecamatan"].map(lambda k: koordinat[k][0])
    d["lon"] = d["kecamatan"].map(lambda k: koordinat[k][1])
    d = d[KOLOM_METEO_FINAL]

    kecamatan_hilang = [k["n"] for k in KECAMATAN_BOGOR if k["n"] not in set(d["kecamatan"])]
    if kecamatan_hilang:
        st.sidebar.info(
            f"{len(kecamatan_hilang)} kecamatan belum ada di data meteorologi, "
            "diisi sementara dari data simulasi: " + ", ".join(kecamatan_hilang)
        )
        pelengkap = df_simulasi[df_simulasi["kecamatan"].isin(kecamatan_hilang)][KOLOM_METEO_FINAL]
        d = pd.concat([d, pelengkap], ignore_index=True)

    return d.reset_index(drop=True)


def compute_risk_index(df_events: pd.DataFrame, df_meteo: pd.DataFrame) -> pd.DataFrame:
    """Indeks risiko komposit SEDERHANA per kecamatan (0-100): gabungan
    jumlah kejadian, rata-rata keparahan, dan curah hujan rata-rata.
    BUKAN metodologi IRBI resmi BNPB — ganti dengan formula kajian
    risiko (bahaya x kerentanan x kapasitas) untuk analisis ilmiah."""
    agg = (
        df_events.groupby("kecamatan")
        .agg(jumlah_kejadian=("kecamatan", "size"), rata_keparahan=("keparahan", "mean"))
        .reset_index()
    )
    out = pd.DataFrame({"kecamatan": [k["n"] for k in KECAMATAN_BOGOR]})
    out = out.merge(agg, on="kecamatan", how="left").fillna({"jumlah_kejadian": 0, "rata_keparahan": 0})
    out = out.merge(df_meteo[["kecamatan", "curah_hujan_mm_hari"]], on="kecamatan", how="left")

    def norm(s):
        rng_ = s.max() - s.min()
        return (s - s.min()) / rng_ if rng_ > 0 else s * 0

    out["indeks_risiko"] = (
        0.45 * norm(out["jumlah_kejadian"])
        + 0.30 * norm(out["rata_keparahan"])
        + 0.25 * norm(out["curah_hujan_mm_hari"])
    ) * 100
    out["indeks_risiko"] = out["indeks_risiko"].round(1)
    out["kategori_risiko"] = pd.cut(
        out["indeks_risiko"], bins=[-1, 33, 66, 101], labels=["Rendah", "Sedang", "Tinggi"]
    )
    return out


# ---------------------------------------------------------------------------
# 4. PEMUATAN DATA
# ---------------------------------------------------------------------------


def _cari_baris_header(uploaded_file):
    """Mencari indeks baris header pada CSV format BPBD (melewati baris
    judul di baris pertama bila ada). Header dikenali dari keberadaan
    kolom KECAMATAN dan BANJIR pada baris yang sama."""
    uploaded_file.seek(0)
    preview = pd.read_csv(uploaded_file, header=None, nrows=5, dtype=str)
    for i in range(len(preview)):
        nilai_baris = set(str(v).strip().upper() for v in preview.iloc[i].tolist())
        if "KECAMATAN" in nilai_baris and "BANJIR" in nilai_baris:
            return i
    return None


def _parse_format_bpbd(uploaded_file):
    """Mem-parse CSV format asli BPBD Kabupaten Bogor. Mengembalikan
    None kalau file tidak cocok format ini (supaya load_data() bisa
    mencoba format lain)."""
    header_idx = _cari_baris_header(uploaded_file)
    if header_idx is None:
        return None

    uploaded_file.seek(0)
    df_raw = pd.read_csv(uploaded_file, skiprows=header_idx, header=0, low_memory=False)
    df_raw.columns = [str(c).strip() for c in df_raw.columns]
    col_lookup = {c.upper(): c for c in df_raw.columns}

    if "KECAMATAN" not in col_lookup or "TANGGAL KEJADIAN" not in col_lookup:
        return None

    def col_num(name):
        key = name.strip().upper()
        if key in col_lookup:
            return pd.to_numeric(df_raw[col_lookup[key]], errors="coerce").fillna(0)
        return pd.Series(0, index=df_raw.index)

    # --- jenis bencana dari 8 kolom biner ---
    ind_df = pd.DataFrame(index=df_raw.index)
    for raw_key, display in TYPE_COLUMN_MAP.items():
        if raw_key in col_lookup:
            ind_df[display] = pd.to_numeric(df_raw[col_lookup[raw_key]], errors="coerce").fillna(0)
    if ind_df.shape[1] == 0:
        return None  # tidak ada satupun kolom jenis bencana ditemukan -> bukan format ini
    has_any = ind_df.sum(axis=1) > 0
    jenis = ind_df.idxmax(axis=1).where(has_any, "Tidak Diketahui")

    # --- tanggal (format M/D/YYYY, dengan fallback parser umum) ---
    tanggal_col = col_lookup["TANGGAL KEJADIAN"]
    tanggal = pd.to_datetime(df_raw[tanggal_col], format="%m/%d/%Y", errors="coerce")
    mask_gagal = tanggal.isna() & df_raw[tanggal_col].notna()
    if mask_gagal.any():
        tanggal.loc[mask_gagal] = pd.to_datetime(df_raw.loc[mask_gagal, tanggal_col], errors="coerce")

    # --- koordinat ---
    lon_col = col_lookup.get("LONGITUDE")
    lat_col = col_lookup.get("LATITUDE")
    lon_parsed = df_raw[lon_col].apply(lambda v: parse_koordinat(v, "lon")) if lon_col else pd.Series(np.nan, index=df_raw.index)
    lat_parsed = df_raw[lat_col].apply(lambda v: parse_koordinat(v, "lat")) if lat_col else pd.Series(np.nan, index=df_raw.index)
    tidak_valid = lon_parsed.isna() | lat_parsed.isna()
    lon_parsed[tidak_valid] = np.nan
    lat_parsed[tidak_valid] = np.nan

    # --- dampak: korban & rumah ---
    meninggal = col_num("MENINGGAL DUNIA (JIWA)")
    luka_berat = col_num("LUKA BERAT (JIWA)")
    luka_sedang = col_num("LUKA SEDANG (JIWA)")
    luka_ringan = col_num("LUKA RINGAN (JIWA)")
    mengungsi_jiwa = col_num("MENGUNGSI (JIWA)")
    rumah_ringan = col_num("RUMAH RUSAK RINGAN")
    rumah_sedang = col_num("RUMAH RUSAK SEDANG")
    rumah_berat = col_num("RUMAH RUSAK BERAT")
    rumah_terancam = col_num("RUMAH TERANCAM")
    rumah_terendam = col_num("RUMAH TERENDAM")
    rumah_terdampak = rumah_ringan + rumah_sedang + rumah_berat + rumah_terancam + rumah_terendam

    # --- keparahan: proksi 1-5 dari kombinasi dampak (lihat catatan di atas file) ---
    dampak_score = (
        meninggal * 5 + luka_berat * 3 + luka_sedang * 2 + luka_ringan * 1
        + rumah_berat * 2 + rumah_sedang * 1 + rumah_ringan * 0.5
        + rumah_terendam * 0.5 + rumah_terancam * 0.3
        + mengungsi_jiwa * 0.02
    )
    max_score = dampak_score.max()
    if max_score > 0:
        keparahan = (1 + 4 * np.log1p(dampak_score) / np.log1p(max_score)).clip(1, 5)
    else:
        keparahan = pd.Series(1.0, index=df_raw.index)

    # --- status (normalisasi + perbaikan salah ketik umum) ---
    status_key = "STATUS KEADAAN DARURAT BENCANA"
    if status_key in col_lookup:
        status = df_raw[col_lookup[status_key]].fillna("Tidak Diketahui").astype(str).str.strip().str.upper()
        status = status.replace({"TANGGAP DARUAT": "TANGGAP DARURAT", "": "TIDAK DIKETAHUI"})
        status = status.str.title()
    else:
        status = pd.Series("Tidak Diketahui", index=df_raw.index)

    hasil = pd.DataFrame(
        {
            "tanggal": tanggal,
            "jenis_bencana": jenis,
            "kecamatan": df_raw[col_lookup["KECAMATAN"]].astype(str).str.strip(),
            "lat": lat_parsed,
            "lon": lon_parsed,
            "meninggal": meninggal.astype(int),
            "mengungsi": mengungsi_jiwa.astype(int),
            "rumah_terdampak": rumah_terdampak.astype(int),
            "keparahan": keparahan.round(1),
            "status": status,
        }
    )
    hasil = hasil.dropna(subset=["tanggal", "kecamatan"])
    hasil = isi_koordinat_otomatis(hasil)
    return hasil


def _parse_format_sederhana(uploaded_file):
    """Mem-parse CSV format sederhana (skema lama): tanggal, jenis_bencana,
    kecamatan wajib ada; lat/lon dan kolom dampak opsional."""
    uploaded_file.seek(0)
    try:
        df_csv = pd.read_csv(uploaded_file, parse_dates=["tanggal"])
    except (ValueError, KeyError):
        return None
    if not {"tanggal", "jenis_bencana", "kecamatan"}.issubset(df_csv.columns):
        return None

    df_csv = isi_koordinat_otomatis(df_csv)
    for kol, default in [
        ("meninggal", 0), ("mengungsi", 0), ("rumah_terdampak", 0),
        ("keparahan", 2.5), ("status", "Tidak Diketahui"),
    ]:
        if kol not in df_csv.columns:
            df_csv[kol] = default
    return df_csv


def load_data(sumber) -> pd.DataFrame:
    """Titik masuk data kejadian bencana. `sumber` adalah daftar
    (nama_file, file_like) dari unggahan CSV (satu/beberapa file) atau
    hasil pembacaan folder — lihat widget_sumber_data(). Tiap file:
    1) coba parse sebagai format asli BPBD Kabupaten Bogor,
    2) kalau gagal, coba format sederhana,
    3) kalau gagal juga, file dilewati dengan pesan di sidebar.
    Semua file yang berhasil dibaca digabung (mis. satu file per bulan).
    Kalau tidak ada sumber, atau tidak satu pun file dikenali, dashboard
    memakai data simulasi."""
    if not sumber:
        return generate_dummy_data()

    bagian = []
    for nama, f in sumber:
        hasil = None
        try:
            hasil = _parse_format_bpbd(f)
            if hasil is None or len(hasil) == 0:
                hasil = _parse_format_sederhana(f)
        except Exception:
            hasil = None
        if hasil is None or len(hasil) == 0:
            st.sidebar.error(
                f"Format CSV '{nama}' tidak dikenali (harus format laporan BPBD "
                "Kabupaten Bogor, atau kolom tanggal, jenis_bencana, kecamatan). Dilewati."
            )
            continue
        bagian.append(hasil)

    if not bagian:
        st.sidebar.error("Tidak ada file kejadian bencana yang bisa dipakai. Menampilkan data simulasi sementara.")
        return generate_dummy_data()

    return pd.concat(bagian, ignore_index=True).sort_values("tanggal", ascending=False).reset_index(drop=True)


def _baca_folder_csv(path_folder: str, sertakan_subfolder: bool = False):
    """Membaca semua file .csv dalam sebuah folder di komputer tempat
    dashboard dijalankan. Mengembalikan (daftar (nama, BytesIO), pesan_error).
    Catatan: yang dibaca adalah folder di mesin yang menjalankan Streamlit;
    kalau dashboard di-hosting online, itu berarti folder di server, bukan
    di komputer pengguna."""
    path_folder = path_folder.strip().strip('"').strip("'")
    if not path_folder:
        return [], None
    if not os.path.isdir(path_folder):
        return [], f"Folder tidak ditemukan: {path_folder}"

    daftar_path = []
    if sertakan_subfolder:
        for akar, _, files in os.walk(path_folder):
            daftar_path += [os.path.join(akar, x) for x in files if x.lower().endswith(".csv")]
    else:
        daftar_path = [
            os.path.join(path_folder, x) for x in os.listdir(path_folder)
            if x.lower().endswith(".csv") and os.path.isfile(os.path.join(path_folder, x))
        ]
    if not daftar_path:
        return [], "Tidak ada file .csv di folder itu."

    sumber = []
    for path in sorted(daftar_path):
        with open(path, "rb") as fh:
            sumber.append((os.path.relpath(path, path_folder), io.BytesIO(fh.read())))
    return sumber, None


# ---------------------------------------------------------------------------
# KOMPONEN UNGGAH: SATU KOTAK UNTUK FOLDER BERISI CSV *ATAU* FILE CSV
# ---------------------------------------------------------------------------
# st.file_uploader bawaan Streamlit tidak bisa memilih folder. Karena itu
# dipakai komponen kecil (HTML+JS, tanpa library tambahan) yang menerima:
#   - seret folder (subfolder ikut dibaca) atau file CSV ke kotak,
#   - klik kotak      -> pilih satu/lebih file CSV,
#   - tautan "pilih folder" -> pilih satu folder.
# Catatan: dialog pilih file di browser tidak bisa sekaligus memilih file dan
# folder, jadi ada satu kotak dengan tiga cara masuk (seret / klik / tautan).
# Berkas komponen ditulis otomatis ke folder sementara saat aplikasi mulai,
# jadi cukup mengunggah dashboard_bencana.py saat hosting. Kalau gagal dibuat,
# dashboard otomatis memakai st.file_uploader biasa (multi-file).
# Isi file dikirim sebagai base64 supaya encoding (mis. simbol derajat)
# tidak rusak. Tiap pemilihan baru MENGGANTI pemilihan sebelumnya.

_HTML_KOMPONEN_UNGGAH = r'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  :root { --teks:#31333F; --latar:#F0F2F6; --garis:#9AA0AD; --aksen:#FF4B4B; }
  html, body { margin:0; padding:0; background:transparent; font-family:"Source Sans Pro", "Segoe UI", sans-serif; }
  #zona { box-sizing:border-box; border:1.5px dashed var(--garis); border-radius:10px; padding:14px 10px 10px;
          text-align:center; color:var(--teks); background:var(--latar); cursor:pointer; }
  #zona.aktif { border-color:var(--aksen); }
  #judul { font-size:14px; line-height:1.35; }
  #judul b { font-weight:600; }
  #tautan { margin-top:6px; font-size:12.5px; }
  .tautan { color:var(--aksen); text-decoration:underline; cursor:pointer; background:none; border:0; padding:0; font:inherit; }
  #status { margin-top:7px; font-size:12.5px; opacity:.85; min-height:16px; }
</style>
</head>
<body>
<div id="zona">
  <div id="judul">Seret <b>folder</b> atau <b>file CSV</b> ke sini,<br>atau klik untuk memilih file CSV</div>
  <div id="tautan">
    <button class="tautan" id="bFolder" type="button">pilih folder</button>
    &nbsp;·&nbsp;
    <button class="tautan" id="bKosong" type="button">kosongkan</button>
  </div>
  <div id="status"></div>
</div>
<input id="inFile" type="file" accept=".csv,text/csv" multiple hidden>
<input id="inFolder" type="file" webkitdirectory hidden>
<script>
(function () {
  var zona = document.getElementById("zona");
  var elStatus = document.getElementById("status");
  var inFile = document.getElementById("inFile");
  var inFolder = document.getElementById("inFolder");

  function kirimKeStreamlit(tipe, data) {
    window.parent.postMessage(Object.assign({ isStreamlitMessage: true, type: tipe }, data), "*");
  }
  function setTinggi() { kirimKeStreamlit("streamlit:setFrameHeight", { height: document.body.scrollHeight + 4 }); }
  function setNilai(v) { kirimKeStreamlit("streamlit:setComponentValue", { value: v, dataType: "json" }); }
  function status(teks) { elStatus.textContent = teks; setTinggi(); }
  function adalahCsv(nama) { return /\.csv$/i.test(nama); }

  function bacaBase64(file) {
    return new Promise(function (res, rej) {
      var r = new FileReader();
      r.onload = function () { var s = String(r.result); res(s.substring(s.indexOf(",") + 1)); };
      r.onerror = function () { rej(r.error); };
      r.readAsDataURL(file);
    });
  }
  function ambilFile(entry) { return new Promise(function (res, rej) { entry.file(res, rej); }); }
  function bacaBatch(reader) { return new Promise(function (res, rej) { reader.readEntries(res, rej); }); }

  async function kumpulkan(entry, awalan, hasil) {
    if (entry.isFile) {
      var f = await ambilFile(entry);
      if (adalahCsv(f.name)) hasil.push({ file: f, nama: awalan + f.name });
    } else if (entry.isDirectory) {
      var reader = entry.createReader();
      var batch;
      do {
        batch = await bacaBatch(reader);
        for (var i = 0; i < batch.length; i++) await kumpulkan(batch[i], awalan + entry.name + "/", hasil);
      } while (batch.length > 0);
    }
  }

  async function kirim(daftar) {
    if (!daftar.length) { status("Tidak ada file .csv yang ditemukan."); return; }
    status("Membaca " + daftar.length + " file...");
    try {
      var files = [];
      for (var i = 0; i < daftar.length; i++) files.push({ name: daftar[i].nama, data: await bacaBase64(daftar[i].file) });
      setNilai({ files: files, waktu: Date.now() });
      status(daftar.length + " file CSV terkirim");
    } catch (err) { status("Gagal membaca file: " + err); }
  }

  zona.addEventListener("click", function (e) {
    if (e.target.closest(".tautan")) return;
    inFile.click();
  });
  document.getElementById("bFolder").addEventListener("click", function (e) { e.stopPropagation(); inFolder.click(); });
  document.getElementById("bKosong").addEventListener("click", function (e) {
    e.stopPropagation(); setNilai({ files: [], waktu: Date.now() }); status("Dikosongkan.");
  });

  inFile.addEventListener("change", function () {
    var d = Array.prototype.slice.call(inFile.files).filter(function (f) { return adalahCsv(f.name); })
      .map(function (f) { return { file: f, nama: f.name }; });
    inFile.value = ""; kirim(d);
  });
  inFolder.addEventListener("change", function () {
    var d = Array.prototype.slice.call(inFolder.files).filter(function (f) { return adalahCsv(f.name); })
      .map(function (f) { return { file: f, nama: f.webkitRelativePath || f.name }; });
    inFolder.value = ""; kirim(d);
  });

  ["dragenter", "dragover"].forEach(function (n) {
    zona.addEventListener(n, function (e) { e.preventDefault(); zona.classList.add("aktif"); });
  });
  zona.addEventListener("dragleave", function () { zona.classList.remove("aktif"); });
  zona.addEventListener("drop", async function (e) {
    e.preventDefault(); zona.classList.remove("aktif");
    var items = e.dataTransfer.items, entries = [];
    if (items && items.length && items[0].webkitGetAsEntry) {
      // harus dikumpulkan secara sinkron sebelum ada await apa pun
      for (var i = 0; i < items.length; i++) { var en = items[i].webkitGetAsEntry(); if (en) entries.push(en); }
    }
    var hasil = [];
    try {
      if (entries.length) { for (var j = 0; j < entries.length; j++) await kumpulkan(entries[j], "", hasil); }
      else { Array.prototype.forEach.call(e.dataTransfer.files, function (f) { if (adalahCsv(f.name)) hasil.push({ file: f, nama: f.name }); }); }
    } catch (err) { status("Gagal membaca folder: " + err); return; }
    kirim(hasil);
  });

  window.addEventListener("message", function (e) {
    if (!e.data || e.data.type !== "streamlit:render") return;
    var t = e.data.theme;
    if (t) {
      var r = document.documentElement.style;
      r.setProperty("--teks", t.textColor); r.setProperty("--latar", t.secondaryBackgroundColor);
      r.setProperty("--aksen", t.primaryColor);
    }
    var a = e.data.args || {};
    if (a.judul) document.getElementById("judul").innerHTML =
      "<b>" + String(a.judul).replace(/</g, "&lt;") + "</b><br>Seret <b>folder</b> atau <b>file CSV</b> ke sini, atau klik untuk memilih file CSV";
    setTinggi();
  });

  kirimKeStreamlit("streamlit:componentReady", { apiVersion: 1 });
  setTinggi();
})();
</script>
</body>
</html>
'''


def _siapkan_komponen_unggah():
    try:
        folder = os.path.join(tempfile.gettempdir(), "dashboard_bencana_komponen_unggah")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "index.html")
        isi_lama = None
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                isi_lama = fh.read()
        if isi_lama != _HTML_KOMPONEN_UNGGAH:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(_HTML_KOMPONEN_UNGGAH)
        return components.declare_component("unggah_csv_atau_folder", path=folder)
    except Exception:
        return None


_unggah_csv = _siapkan_komponen_unggah()


def _sumber_dari_komponen(nilai):
    """Mengubah nilai dari komponen ({"files": [{"name", "data": base64}]})
    menjadi daftar (nama_file, BytesIO) seperti hasil st.file_uploader."""
    hasil = []
    if not isinstance(nilai, dict):
        return hasil
    for f in nilai.get("files", []) or []:
        try:
            hasil.append((str(f["name"]), io.BytesIO(base64.b64decode(f["data"]))))
        except Exception:
            continue
    return hasil


def _pilih_folder_dialog(judul: str = "Pilih folder"):
    """Membuka jendela pilih-folder bawaan sistem operasi (lewat tkinter,
    dijalankan di proses terpisah supaya aman dari Streamlit).
    Mengembalikan path folder, "" kalau dibatalkan, atau None kalau
    jendelanya tidak bisa dibuka (mis. dashboard berjalan di server
    tanpa layar). Ini bekerja karena dashboard dijalankan di komputer
    pengguna sendiri; pada versi yang di-hosting online, jendela ini
    akan muncul di server, bukan di komputer pengguna."""
    kode = (
        "import tkinter as tk\n"
        "from tkinter import filedialog\n"
        "r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True)\n"
        f"print(filedialog.askdirectory(title={judul!r}))\n"
    )
    try:
        hasil = subprocess.run(
            [sys.executable, "-c", kode], capture_output=True, text=True, timeout=300
        )
    except Exception:
        return None
    if hasil.returncode != 0:
        return None
    return hasil.stdout.strip()


def _klik_pilih_folder(kunci: str, judul: str):
    """Callback tombol "Pilih folder...": isi kolom path dari jendela pilih-folder."""
    path = _pilih_folder_dialog(f"Pilih folder: {judul}")
    if path is None:
        st.session_state[f"galat_dialog_{kunci}"] = True
    else:
        st.session_state[f"galat_dialog_{kunci}"] = False
        if path:  # "" berarti dibatalkan -> biarkan path lama
            st.session_state[f"folder_{kunci}"] = os.path.normpath(path)


def widget_sumber_data(kunci: str, judul: str, bantuan: str, contoh_path: str):
    """Widget sidebar untuk memilih sumber data: unggah file CSV (boleh
    lebih dari satu) ATAU pilih sebuah folder lewat jendela pilih-folder
    (path juga bisa diketik/ditempel manual). Mengembalikan daftar
    (nama_file, file_like); daftar kosong berarti tidak ada sumber."""
    st.markdown(f"**{judul}**")
    if IZINKAN_PILIH_FOLDER_SERVER:
        mode = st.radio(
            "Sumber data", ["Unggah file CSV", "Pilih folder"],
            horizontal=True, key=f"mode_{kunci}", label_visibility="collapsed",
        )
    else:
        mode = "Unggah file CSV"
    if mode == "Unggah file CSV" and _unggah_csv is not None:
        nilai = _unggah_csv(judul=judul, key=f"komp_{kunci}", default={"files": []})
        sumber = _sumber_dari_komponen(nilai)
        if sumber:
            nama = [n for n, _ in sumber]
            st.caption(
                f"{len(sumber)} file CSV diterima: " + ", ".join(nama[:3])
                + (f", +{len(nama) - 3} lainnya" if len(nama) > 3 else "")
            )
        return sumber
    if mode == "Unggah file CSV":
        files = st.file_uploader(
            "File CSV", type=["csv"], accept_multiple_files=True,
            key=f"upload_{kunci}", label_visibility="collapsed",
            help=bantuan + " Bisa memilih banyak file sekaligus, atau menyeret "
            "sebuah folder berisi CSV ke kotak ini.",
        )
        return [(f.name, f) for f in (files or [])]

    st.button(
        "Pilih folder...", key=f"btn_{kunci}", on_click=_klik_pilih_folder,
        args=(kunci, judul), use_container_width=True,
        help="Membuka jendela untuk memilih folder berisi file CSV. " + bantuan,
    )
    if st.session_state.get(f"galat_dialog_{kunci}"):
        st.warning(
            "Jendela pilih folder tidak bisa dibuka di sini (mis. dashboard "
            "berjalan di server). Ketik path folder secara manual di bawah, "
            "atau pakai opsi Unggah file CSV."
        )
    path = st.text_input(
        "Folder terpilih (bisa juga diketik/ditempel)", key=f"folder_{kunci}",
        placeholder=contoh_path,
    )
    sub = st.checkbox("Sertakan subfolder", key=f"sub_{kunci}")
    sumber, pesan = _baca_folder_csv(path, sub)
    if pesan:
        st.warning(pesan)
    elif sumber:
        st.caption(f"{len(sumber)} file CSV terbaca dari folder.")
    return sumber


# ---------------------------------------------------------------------------
# 5. SIDEBAR: FILTER
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### Pengaturan Data")
    sumber_bencana = widget_sumber_data(
        "bencana", "Data kejadian bencana (opsional)",
        "Mendukung format asli laporan BPBD Kabupaten Bogor (terdeteksi otomatis) "
        "maupun format sederhana; beberapa file akan digabung. Kosongkan untuk "
        "memakai data simulasi.",
        r"C:\Users\nama\data_bencana",
    )
    sumber_meteo = widget_sumber_data(
        "meteo", "Data meteorologi per kecamatan (opsional)",
        "Kolom wajib: kecamatan, curah hujan (nama kolom fleksibel). Kolom "
        "opsional: suhu, kelembaban, kecepatan angin. Kecamatan yang tidak ada "
        "akan diisi sementara dari data simulasi.",
        r"C:\Users\nama\data_meteorologi",
    )
    ada_data_bencana = len(sumber_bencana) > 0
    ada_data_meteo = len(sumber_meteo) > 0

    st.markdown("---")
    st.markdown("### Filter")

    df_all = load_data(sumber_bencana)
    df_meteo = load_meteo_data(sumber_meteo)

    tahun_opsi = sorted(df_all["tanggal"].dt.year.unique(), reverse=True)
    tahun_pilih = st.multiselect("Tahun", tahun_opsi, default=tahun_opsi)

    NAMA_BULAN = {
        1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
        7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember",
    }
    # Opsi bulan hanya diambil dari data pada tahun yang sedang dipilih, supaya
    # daftar bulannya relevan (mis. kalau data 2026 baru sampai September,
    # bulan Oktober-Desember tidak muncul di daftar).
    df_untuk_opsi_bulan = df_all[df_all["tanggal"].dt.year.isin(tahun_pilih)] if tahun_pilih else df_all
    bulan_angka_tersedia = sorted(df_untuk_opsi_bulan["tanggal"].dt.month.unique())
    bulan_opsi = [NAMA_BULAN[b] for b in bulan_angka_tersedia]
    bulan_pilih_nama = st.multiselect(
        "Bulan", bulan_opsi, default=[], placeholder="Semua bulan"
    )
    NAMA_KE_ANGKA_BULAN = {v: k for k, v in NAMA_BULAN.items()}
    bulan_pilih_angka = [NAMA_KE_ANGKA_BULAN[b] for b in bulan_pilih_nama]

    jenis_opsi = sorted(df_all["jenis_bencana"].unique())
    jenis_pilih = st.multiselect("Jenis bencana", jenis_opsi, default=jenis_opsi)

    kecamatan_opsi = sorted(df_all["kecamatan"].unique())
    kecamatan_pilih = st.multiselect(
        "Kecamatan", kecamatan_opsi, default=[], placeholder="Semua kecamatan"
    )

    st.markdown("---")
    st.caption(
        "Prototipe untuk Departemen Geofisika dan Meteorologi, IPB "
        "University. Cakupan: Kabupaten Bogor."
    )

df = df_all[df_all["tanggal"].dt.year.isin(tahun_pilih) & df_all["jenis_bencana"].isin(jenis_pilih)]
if bulan_pilih_angka:
    df = df[df["tanggal"].dt.month.isin(bulan_pilih_angka)]
if kecamatan_pilih:
    df = df[df["kecamatan"].isin(kecamatan_pilih)]

df_risk = compute_risk_index(df, df_meteo)


# ---------------------------------------------------------------------------
# 5.5 BAR LOGO (kanan atas, sejajar tab) & PETA HASIL ANALISIS BENCANA 2026
# ---------------------------------------------------------------------------


def html_logo_bar() -> str:
    """Membuat bar logo (IPB, BPBD, BMKG) sebagai HTML dengan gambar
    ter-embed base64, supaya bisa diposisikan lewat CSS di ujung kanan
    sejajar tombol tab. Logo yang filenya belum ada dilewati. File logo
    dicari di folder LOGO_DIR (logo_ipb, logo_bpbd, logo_bmkg; format
    png/jpg/jpeg)."""
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}
    img_tags = []
    for label, nama_file in [
        ("IPB University", "logo_ipb"),
        ("BPBD Kab. Bogor", "logo_bpbd"),
        ("BMKG", "logo_bmkg"),
    ]:
        for ext in ["png", "jpg", "jpeg"]:
            path = os.path.join(LOGO_DIR, f"{nama_file}.{ext}")
            if os.path.exists(path):
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                img_tags.append(f'<img src="data:{mime[ext]};base64,{b64}" alt="{label}" title="{label}">')
                break
    if not img_tags:
        return ""
    return f'<div class="logo-bar">{"".join(img_tags)}</div>'


_logo_html = html_logo_bar()
if _logo_html:
    st.markdown(_logo_html, unsafe_allow_html=True)


# Peta pada bagian ini BUKAN digambar otomatis dari data kejadian di atas,
# melainkan hasil analisis yang sudah disiapkan terpisah (mis. dari QGIS/
# ArcGIS/Kepler.gl) untuk tahun 2026, satu peta per jenis bencana. Taruh
# berkasnya di folder PETA_ANALISIS_DIR di samping file dashboard ini,
# dengan pola nama: peta_<jenis_bencana>_2026.<ekstensi>
#   - <jenis_bencana>: huruf kecil, spasi diganti underscore
#     (contoh: "Tanah Longsor" -> tanah_longsor, "Angin Kencang" -> angin_kencang)
#   - <ekstensi>: png/jpg/jpeg untuk gambar statis (hasil ekspor peta biasa),
#     atau html untuk peta interaktif (hasil ekspor Folium/Kepler.gl/dst.)
# Contoh nama file yang benar:
#   peta_analisis/peta_banjir_2026.png
#   peta_analisis/peta_tanah_longsor_2026.html

PETA_ANALISIS_DIR = "peta_analisis"
JENIS_PETA_2026 = ["Banjir", "Tanah Longsor", "Kebakaran", "Kekeringan", "Angin Kencang", "Karhutla"]


def slug_jenis_peta(nama: str) -> str:
    return nama.strip().lower().replace(" ", "_")


def cari_file_peta(jenis: str):
    """Mencari berkas peta hasil analisis untuk satu jenis bencana.
    Mengembalikan (path, ekstensi) atau (None, None) kalau belum ditemukan."""
    slug = slug_jenis_peta(jenis)
    for ext in ["png", "jpg", "jpeg", "html"]:
        path = os.path.join(PETA_ANALISIS_DIR, f"peta_{slug}_2026.{ext}")
        if os.path.exists(path):
            return path, ext
    return None, None


tab_utama, tab_peta_2026 = st.tabs(["Dashboard Utama", "Peta Analisis 2026"])

with tab_utama:
    # ---------------------------------------------------------------------------
    # 6. HEADER & BARIS KPI
    # ---------------------------------------------------------------------------

    st.markdown("## Pemantauan Bencana — Kabupaten Bogor")
    st.markdown(
        '<p class="dash-caption">Departemen Geofisika dan Meteorologi, IPB '
        "University · cakupan Kabupaten Bogor.</p>",
        unsafe_allow_html=True,
    )
    if not ada_data_bencana or not ada_data_meteo:
        bagian_kurang = []
        if not ada_data_bencana:
            bagian_kurang.append("kejadian bencana")
        if not ada_data_meteo:
            bagian_kurang.append("meteorologi")
        st.markdown(
            '<div class="proto-note">📌 Data ' + " & ".join(bagian_kurang) + " masih "
            "<b>simulasi</b>. Unggah CSV yang sesuai di sidebar untuk melihat data "
            "sebenarnya.</div>",
            unsafe_allow_html=True,
        )

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total kejadian", f"{len(df):,}".replace(",", "."))
    col2.metric("Korban meninggal", f"{int(df['meninggal'].sum()):,}".replace(",", "."))
    col3.metric("Korban mengungsi", f"{int(df['mengungsi'].sum()):,}".replace(",", "."))
    col4.metric("Rumah terdampak", f"{int(df['rumah_terdampak'].sum()):,}".replace(",", "."))
    n_tinggi = int((df_risk["kategori_risiko"] == "Tinggi").sum())
    col5.metric("Kecamatan risiko tinggi", f"{n_tinggi} / {len(KECAMATAN_BOGOR)}")

    st.markdown("---")

    # ---------------------------------------------------------------------------
    # 7 & 8. PETA SEBARAN + TREN BULANAN
    # ---------------------------------------------------------------------------

    left, right = st.columns([1.55, 1])

    with left:
        st.markdown("#### Sebaran titik kejadian")
        st.caption(
            "Ukuran titik = indeks keparahan relatif kejadian. Peta memakai basemap "
            "OpenStreetMap (butuh koneksi internet). Titik tanpa koordinat asli "
            "ditempatkan di sekitar titik tengah kecamatan."
        )

        fig_map = go.Figure()
        for jenis in jenis_opsi:
            sub = df[df["jenis_bencana"] == jenis]
            if sub.empty:
                continue
            fig_map.add_trace(
                go.Scattermap(
                    lat=sub["lat"],
                    lon=sub["lon"],
                    mode="markers",
                    name=jenis,
                    text=sub.apply(
                        lambda r: f"{r['jenis_bencana']}<br>{r['kecamatan']}<br>{r['tanggal'].strftime('%d %b %Y')}",
                        axis=1,
                    ),
                    hoverinfo="text",
                    marker=dict(size=(sub["keparahan"] * 3.2 + 6), color=PALETTE.get(jenis, "#999999"), opacity=0.85),
                )
            )
        fig_map.update_layout(
            map=dict(style="open-street-map", center=MAP_CENTER, zoom=MAP_ZOOM),
            margin=dict(l=0, r=0, t=0, b=0),
            height=420,
            legend=dict(orientation="h", y=-0.03),
        )
        st.plotly_chart(fig_map, use_container_width=True)

        st.markdown("#### Tren bulanan")
        st.caption("Jumlah kejadian tercatat per bulan, dipecah menurut jenis.")
        df_trend = df.copy()
        df_trend["bulan"] = df_trend["tanggal"].dt.to_period("M").astype(str)
        trend_agg = df_trend.groupby(["bulan", "jenis_bencana"]).size().reset_index(name="jumlah")
        fig_trend = px.bar(
            trend_agg, x="bulan", y="jumlah", color="jenis_bencana", color_discrete_map=PALETTE,
            labels={"bulan": "", "jumlah": "Jumlah kejadian", "jenis_bencana": "Jenis"},
        )
        fig_trend.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="")
        st.plotly_chart(fig_trend, use_container_width=True)

    with right:
        st.markdown("#### Komposisi jenis bencana")
        comp = df["jenis_bencana"].value_counts().reset_index()
        comp.columns = ["jenis_bencana", "jumlah"]
        fig_comp = px.pie(
            comp, names="jenis_bencana", values="jumlah", hole=0.55,
            color="jenis_bencana", color_discrete_map=PALETTE,
        )
        fig_comp.update_layout(height=230, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="")
        st.plotly_chart(fig_comp, use_container_width=True)

        st.markdown("#### Sebaran per kecamatan")
        st.caption("10 kecamatan dengan kejadian terbanyak.")
        kec_rank = df["kecamatan"].value_counts().head(10).sort_values().reset_index()
        kec_rank.columns = ["kecamatan", "jumlah"]
        fig_kec = px.bar(kec_rank, x="jumlah", y="kecamatan", orientation="h", color_discrete_sequence=["#E1863C"])
        fig_kec.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
        st.plotly_chart(fig_kec, use_container_width=True)

    st.markdown("---")

    # ---------------------------------------------------------------------------
    # 9. KORELASI METEOROLOGI x KEJADIAN BENCANA, DENGAN INDEKS RISIKO
    # ---------------------------------------------------------------------------

    st.markdown("#### Korelasi intensitas meteorologi vs kejadian bencana per kecamatan")
    st.caption(
        "Sumbu X: curah hujan rata-rata (mm/hari). Sumbu Y: jumlah kejadian "
        "hidrometeorologi (banjir, tanah longsor, angin kencang, kekeringan). Ukuran "
        "titik: total seluruh jenis kejadian. Warna: kategori indeks risiko komposit "
        "(lihat catatan di kode, bukan IRBI resmi)."
    )

    hidro_count = (
        df[df["jenis_bencana"].isin(HIDROMETEOROLOGI)]
        .groupby("kecamatan").size().reset_index(name="kejadian_hidrometeorologi")
    )
    corr_df = df_risk.merge(hidro_count, on="kecamatan", how="left").fillna({"kejadian_hidrometeorologi": 0})

    fig_corr = px.scatter(
        corr_df,
        x="curah_hujan_mm_hari",
        y="kejadian_hidrometeorologi",
        size="jumlah_kejadian",
        color="kategori_risiko",
        color_discrete_map=RISK_COLOR,
        hover_name="kecamatan",
        hover_data={"indeks_risiko": True, "rata_keparahan": ":.1f", "jumlah_kejadian": True,
                    "curah_hujan_mm_hari": ":.1f", "kejadian_hidrometeorologi": True},
        labels={
            "curah_hujan_mm_hari": "Curah hujan rata-rata (mm/hari)",
            "kejadian_hidrometeorologi": "Jumlah kejadian hidrometeorologi",
            "kategori_risiko": "Indeks risiko",
        },
        size_max=32,
    )

    # --- Regresi linear sederhana (least squares) & R² ---
    # R² (koefisien determinasi) mengukur seberapa besar variasi jumlah
    # kejadian hidrometeorologi yang bisa dijelaskan oleh curah hujan secara
    # linear: 0 = tidak ada hubungan linear sama sekali, 1 = hubungan linear
    # sempurna. Dihitung manual dengan numpy.polyfit supaya tidak perlu
    # menginstal statsmodels (dipakai oleh trendline bawaan Plotly Express).
    x_vals = corr_df["curah_hujan_mm_hari"].to_numpy(dtype=float)
    y_vals = corr_df["kejadian_hidrometeorologi"].to_numpy(dtype=float)

    r_squared = np.nan
    if len(x_vals) >= 2 and np.std(x_vals) > 0:
        slope, intercept = np.polyfit(x_vals, y_vals, 1)
        y_pred = slope * x_vals + intercept
        ss_res = np.sum((y_vals - y_pred) ** 2)
        ss_tot = np.sum((y_vals - y_vals.mean()) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        r_koefisien = np.sign(slope) * np.sqrt(r_squared)  # koefisien korelasi Pearson (r)

        x_garis = np.linspace(x_vals.min(), x_vals.max(), 50)
        y_garis = slope * x_garis + intercept
        fig_corr.add_trace(
            go.Scatter(
                x=x_garis, y=y_garis, mode="lines", name="Garis regresi",
                line=dict(color="#5E6B7A", width=2, dash="dash"),
                hoverinfo="skip",
            )
        )
        fig_corr.add_annotation(
            xref="paper", yref="paper", x=0.02, y=0.98, xanchor="left", yanchor="top",
            showarrow=False,
            text=f"R² = {r_squared:.3f}  (r = {r_koefisien:.3f})<br>y = {slope:.3f}x + {intercept:.2f}",
            font=dict(size=12, color="#3A4552"),
            align="left", bgcolor="rgba(255,255,255,0.75)",
            bordercolor="rgba(127,127,127,0.35)", borderwidth=1, borderpad=6,
        )

    fig_corr.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="Indeks risiko")
    st.plotly_chart(fig_corr, use_container_width=True)

    if not np.isnan(r_squared):
        if r_squared >= 0.64:
            kekuatan = "kuat"
        elif r_squared >= 0.36:
            kekuatan = "sedang"
        elif r_squared >= 0.09:
            kekuatan = "lemah"
        else:
            kekuatan = "sangat lemah / tidak ada"
        arah = "positif" if r_koefisien >= 0 else "negatif"
        st.caption(
            f"R² = {r_squared:.3f} berarti sekitar {r_squared*100:.1f}% variasi jumlah kejadian "
            f"hidrometeorologi antar-kecamatan bisa dijelaskan secara linear oleh curah hujan "
            f"rata-rata pada data saat ini — hubungan {arah} dengan kekuatan **{kekuatan}** "
            f"(patokan kasar: R² < 0,09 sangat lemah, 0,09–0,36 lemah, 0,36–0,64 sedang, > 0,64 kuat). "
            "Ini korelasi sederhana, bukan bukti sebab-akibat, dan sangat dipengaruhi jumlah "
            "titik data (baru 40 kecamatan)."
        )
    else:
        st.caption("R² belum bisa dihitung — data curah hujan tidak bervariasi atau titik data kurang dari 2.")

    st.markdown("---")

    # ---------------------------------------------------------------------------
    # 10. INDIKATOR METEOROLOGI PER KECAMATAN
    # ---------------------------------------------------------------------------

    st.markdown("#### Indikator meteorologi")
    st.caption(
        "Nilai rata-rata seluruh kecamatan."
        if ada_data_meteo else
        "Nilai rata-rata seluruh kecamatan (data simulasi)."
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Curah Hujan (mm/hari)", f"{df_meteo['curah_hujan_mm_hari'].mean():.1f}")
    m2.metric("Suhu (°C)", f"{df_meteo['suhu_c'].mean():.1f}")
    m3.metric("Kelembaban (%)", f"{df_meteo['kelembaban_persen'].mean():.0f}")
    m4.metric("Kecepatan Angin (km/jam)", f"{df_meteo['kecepatan_angin_kmh'].mean():.1f}")

    tab1, tab2 = st.tabs(["Curah hujan per kecamatan", "Tabel indikator lengkap"])

    with tab1:
        meteo_sorted = df_meteo.sort_values("curah_hujan_mm_hari", ascending=True)
        fig_meteo = px.bar(
            meteo_sorted, x="curah_hujan_mm_hari", y="kecamatan", orientation="h",
            color="kategori_intensitas",
            color_discrete_map={
                "Tidak Hujan/Berawan": "#8A96A5", "Ringan": "#3FA79E",
                "Sedang": "#D9A441", "Lebat": "#E1863C", "Sangat Lebat": "#E8543F",
            },
            labels={"curah_hujan_mm_hari": "Curah hujan (mm/hari)", "kecamatan": "", "kategori_intensitas": "Kategori"},
        )
        fig_meteo.update_layout(height=760, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="")
        st.plotly_chart(fig_meteo, use_container_width=True)

    with tab2:
        tabel_meteo = df_meteo[
            ["kecamatan", "curah_hujan_mm_hari", "kategori_intensitas", "suhu_c", "kelembaban_persen", "kecepatan_angin_kmh"]
        ].sort_values("curah_hujan_mm_hari", ascending=False)
        tabel_meteo.columns = ["Kecamatan", "Curah Hujan (mm/hari)", "Kategori", "Suhu (°C)", "Kelembaban (%)", "Angin (km/jam)"]
        st.dataframe(tabel_meteo, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ---------------------------------------------------------------------------
    # 11. LOG KEJADIAN TERBARU
    # ---------------------------------------------------------------------------

    st.markdown("#### Log kejadian terbaru")
    log_cols = ["tanggal", "jenis_bencana", "kecamatan", "meninggal", "mengungsi", "rumah_terdampak", "status"]
    df_log = df.sort_values("tanggal", ascending=False)[log_cols].head(30).copy()
    df_log["tanggal"] = df_log["tanggal"].dt.strftime("%d %b %Y")
    df_log.columns = ["Tanggal", "Jenis", "Kecamatan", "Meninggal", "Mengungsi", "Rumah Terdampak", "Status"]
    st.dataframe(df_log, use_container_width=True, hide_index=True)

    st.caption(
        "Indeks risiko adalah komposit sederhana untuk keperluan prototipe. Sesuaikan "
        "metodologinya sebelum dipakai untuk analisis atau laporan resmi."
    )

with tab_peta_2026:
    st.markdown("### Peta Hasil Analisis Bencana 2026")
    st.caption(
        "Peta hasil analisis kebencanaan Kabupaten Bogor tahun 2026, dipilih per "
        "jenis bencana. Peta ini hasil analisis yang sudah disiapkan terpisah, "
        "bukan digambar otomatis dari data kejadian di tab \"Dashboard Utama\"."
    )

    jenis_peta_pilih = st.radio(
        "Pilih jenis bencana", JENIS_PETA_2026, horizontal=True, key="peta2026_jenis"
    )

    path_peta, ext_peta = cari_file_peta(jenis_peta_pilih)
    if path_peta is None:
        st.warning(
            f"Berkas peta untuk **{jenis_peta_pilih}** belum ditemukan. Taruh file "
            f"peta di folder `{PETA_ANALISIS_DIR}/` (sejajar dengan dashboard_bencana.py) "
            f"dengan nama `peta_{slug_jenis_peta(jenis_peta_pilih)}_2026.png` (atau "
            ".jpg/.jpeg untuk gambar statis, .html untuk peta interaktif hasil ekspor "
            "Folium/Kepler.gl/dst.)."
        )
    elif ext_peta == "html":
        with open(path_peta, "r", encoding="utf-8") as f:
            html_peta = f.read()
        st.components.v1.html(html_peta, height=650, scrolling=True)
    else:
        st.image(
            path_peta,
            caption=f"Peta {jenis_peta_pilih} — Kabupaten Bogor, 2026",
            use_container_width=True,
        )
