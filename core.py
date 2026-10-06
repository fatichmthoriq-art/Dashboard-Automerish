"""Fungsi inti: baca data UTM, pipeline perapian kurva (smoothing, toe, patah), koreksi ML opsional, grafik.
Fungsi fitur() harus identik dengan notebook pelatihan."""
import io
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
from scipy.interpolate import make_smoothing_spline

# ----------------------------------------------------------------------------- baca file
X_KW = ['elong', 'extens', 'deflek', 'deflect', 'displace', 'perpanjang', 'pertambahan', 'strain',
        'regang', 'stroke', 'posisi', 'position', '(mm)', '( mm)', 'mm)']
Y_KW = ['force', 'load', 'beban', 'gaya', 'stress', 'tegang', '(n)', '( n)', 'kn)', 'kgf', 'mpa', 'n/mm']
SKIP = r'^\s*no\.?\s*$|nomor|time|waktu|\(\s*min|\(\s*s\)|detik|sec|index'


def _to_num(s):
    if not pd.api.types.is_numeric_dtype(s):
        s = s.astype(str).str.strip().str.replace(' ', '', regex=False)
        s = s.where(~s.str.contains(r'\d\.\d{3},'), s.str.replace('.', '', regex=False))
        s = s.str.replace(',', '.', regex=False)
    return pd.to_numeric(s, errors='coerce')


def baca_tabel(nama, data: bytes):
    n = nama.lower()
    if n.endswith(('.xlsx', '.xlsm', '.xls')):
        return pd.read_excel(io.BytesIO(data), sheet_name=None, header=None)
    head = data[:5000].decode('utf-8', 'ignore')
    sep = '\t' if '\t' in head else ';' if ';' in head else ',' if ',' in head else r'\s+'
    return {'csv': pd.read_csv(io.BytesIO(data), header=None, sep=sep, engine='python', dtype=str,
                               encoding_errors='ignore', on_bad_lines='skip')}


def ambil_kurva(df, min_titik=5):
    """Pilih kolom X (elongation) & Y (force) dari judul kolom; cadangan: pasangan kolom numerik."""
    num = df.apply(_to_num)
    kolom = [c for c in num.columns if num[c].notna().sum() >= min_titik]
    judul = {}
    for c in kolom:
        i0 = num[c].first_valid_index()
        t = [str(v) for v in df.loc[:i0, c].dropna() if not re.fullmatch(r'[\d\s.,eE+-]*', str(v))]
        judul[c] = ' '.join(t).strip()
    cocok = lambda c, kw: any(k in judul[c].lower() for k in kw)
    xs = [c for c in kolom if cocok(c, X_KW) and not cocok(c, Y_KW)]
    ys = [c for c in kolom if cocok(c, Y_KW)]
    if xs and ys:
        pasang = []
        for cy in ys:
            kiri = [c for c in xs if kolom.index(c) < kolom.index(cy)] or xs
            pasang.append((kiri[-1], cy))
    else:
        bersih = [c for c in kolom if not re.search(SKIP, judul[c].lower())]
        bersih = [c for c in bersih if not (np.allclose(np.diff(num[c].dropna()), 1)
                                            and num[c].dropna().iloc[0] in (0, 1))]
        pasang = [(bersih[i], bersih[i + 1]) for i in range(0, len(bersih) - 1, 2)]
    hasil = []
    for cx, cy in pasang:
        d = num[[cx, cy]].dropna()
        d = d[np.isfinite(d[cx]) & np.isfinite(d[cy])]
        if len(d) >= min_titik:
            hasil.append(dict(x=d[cx].to_numpy(float), y=d[cy].to_numpy(float),
                              kolom_x=judul[cx] or f'kolom {cx}', kolom_y=judul[cy] or f'kolom {cy}'))
    return hasil


def kurva_dari_file(nama, data):
    out = []
    for sh, df in baca_tabel(nama, data).items():
        for k in ambil_kurva(df):
            k['sheet'] = sh
            out.append(k)
    return out


# ----------------------------------------------------------------------------- fitur model
def bersihkan(x, y):
    m = np.isfinite(x) & np.isfinite(y); x, y = x[m], y[m]
    o = np.argsort(x, kind='stable'); x, y = x[o], y[o]
    u, inv = np.unique(np.round(x, 12), return_inverse=True)
    return u, np.bincount(inv, weights=y) / np.bincount(inv)


def norm_param(x, y):
    x0, x1 = x.min(), x.max(); ys = np.abs(y).max() or 1.0
    return x0, (x1 - x0) or 1.0, ys


def fitur(xr, yr, xq, win):
    F = {}
    yi = np.interp(xq, xr, yr); F['interp'] = yi
    F['pos'] = xq
    F['diluar'] = np.clip(xr[0] - xq, 0, None) + np.clip(xq - xr[-1], 0, None)
    idx = np.searchsorted(xr, xq)
    F['jarak_terdekat'] = np.minimum(np.abs(xq - xr[np.clip(idx - 1, 0, len(xr) - 1)]),
                                     np.abs(xr[np.clip(idx, 0, len(xr) - 1)] - xq))
    ipk = np.argmax(yr); F['rel_puncak'] = xq - xr[ipk]; F['y_puncak'] = np.full_like(xq, yr[ipk])
    for w in win:
        lo = np.searchsorted(xr, xq - w); hi = np.searchsorted(xr, xq + w)
        F[f'n_{w}'] = hi - lo
        fit, slope, sd = yi.copy(), np.full_like(xq, np.nan), np.full_like(xq, np.nan)
        for i, (l, h) in enumerate(zip(lo, hi)):
            if h - l < 3:
                continue
            xx, yy = xr[l:h] - xq[i], yr[l:h]
            sw = np.sqrt(np.clip(1 - (np.abs(xx) / w) ** 3, 0, None) ** 3)
            A = np.vstack([np.ones_like(xx), xx, xx ** 2]).T
            try:
                c, *_ = np.linalg.lstsq(A * sw[:, None], yy * sw, rcond=None)
                fit[i], slope[i], sd[i] = c[0], c[1], np.std(yy - A @ c)
            except np.linalg.LinAlgError:
                pass
        F[f'lowess_{w}'] = fit - yi; F[f'slope_{w}'] = slope; F[f'sd_{w}'] = sd
    return pd.DataFrame(F)


# ----------------------------------------------------------------------------- pipeline perapian
SATUAN_X = {'mm': 1.0, 'cm': 0.1, 'm': 1e-3, 'in': 1 / 25.4}
SATUAN_Y = {'N': 1.0, 'kN': 1e-3, 'kgf': 1 / 9.80665, 'lbf': 0.224809}


def step_otomatis(rentang, n=200):
    kasar = rentang / n; e = 10 ** np.floor(np.log10(kasar))
    return min([1, 2, 2.5, 5, 10], key=lambda m: abs(m * e - kasar)) * e


def _grid_halus(xr, yr, n=1000):
    g = np.linspace(xr[0], xr[-1], n)
    gy = np.interp(g, xr, yr)
    return g, savgol_filter(gy, max(7, (n // 60) | 1), 2)


def deteksi_patah(xr, yr, metode='otomatis', frac=0.4, drop=0.15):
    """Kembalikan elongation tepat sebelum spesimen patah.
    otomatis : beban jatuh > drop*puncak dalam jarak pendek (~1.5% rentang) setelah puncak
    fraksi   : beban pertama kali < frac*puncak setelah puncak"""
    if metode == 'tidak':
        return xr[-1]
    g, gy = _grid_halus(xr, yr)
    ip = int(np.argmax(gy)); pk = gy[ip]
    if metode == 'fraksi':
        t = np.where(gy[ip:] < frac * pk)[0]
        return g[ip + t[0]] if len(t) else xr[-1]
    w = max(3, int(0.015 * len(g)))
    for i in range(ip, len(g) - w):
        if gy[i] - gy[i + w] > drop * pk:
            return g[i]
    t = np.where(gy[ip:] < 0.05 * pk)[0]
    return g[ip + t[0]] if len(t) else xr[-1]


def daerah_linear(xr, yr, lo=0.10, hi=0.60):
    """Cari daerah elastis (kemiringan terbesar) sebelum puncak; kembalikan (m, c, x_awal, x_akhir)."""
    g, gy = _grid_halus(xr, yr)
    ip = int(np.argmax(gy)); pk = gy[ip]
    d = np.gradient(gy, g)
    ok = np.where((gy[:ip + 1] > lo * pk) & (gy[:ip + 1] < hi * pk))[0]
    if len(ok) < 5:
        return None
    k = ok[np.argmax(d[ok])]
    sel = ok[d[ok] >= 0.85 * d[k]]
    sel = sel[(sel >= sel[sel <= k].min()) & (sel <= sel[sel >= k].max())]
    xa, xb = g[sel[0]], g[sel[-1]]
    m_ = (xr >= xa) & (xr <= xb)
    if m_.sum() < 3:
        return None
    m, c = np.polyfit(xr[m_], yr[m_], 1)
    return m, c, xa, xb


def proses(x_raw, y_raw, awal='nol', patah='otomatis', frac=0.4, kehalusan=5, step='auto',
           paket=None, pakai_ml=False):
    """Pipeline perapian. Kembalikan (x_grid, y_grid, info) dalam satuan asli (mm, N)."""
    xr, yr = bersihkan(np.asarray(x_raw, float), np.asarray(y_raw, float))
    if len(xr) < 8:
        raise ValueError('data terlalu sedikit (< 8 titik)')
    info = {'F_maks_mentah': float(yr.max())}
    # 1. potong saat patah
    xe = deteksi_patah(xr, yr, patah, frac)
    m_ = xr <= xe
    if m_.sum() >= 8:
        xr, yr = xr[m_], yr[m_]
    info['x_patah_asli'] = float(xr[-1])
    # 2. awal kurva
    lin = daerah_linear(xr, yr)
    info['kekakuan'] = float(lin[0]) if lin else np.nan
    geser = 0.0
    if awal == 'toe' and lin:
        m, c, xa, _ = lin
        x0 = -c / m                                     # perpotongan garis elastis dengan F = 0
        keep = xr >= xa
        xr = np.r_[x0, xr[keep]]; yr = np.r_[0.0, yr[keep]]
        geser = x0; xr = xr - x0
    elif awal == 'nol':
        # buang daerah 'toe' (beban kecil yang datar/bergelombang di awal), lalu tarik dari (0,0)
        xa = lin[2] if lin else 0.0
        keep = xr >= xa if xa > 0 else xr > 0
        xr = np.r_[0.0, xr[keep]]; yr = np.r_[0.0, yr[keep]]
    info['geser_toe'] = float(geser)
    # 3. grid keluaran
    rentang = xr[-1] - xr[0]
    st = step_otomatis(rentang) if step in (None, 'auto') else float(step)
    xg = np.arange(xr[0], xr[-1] + st * 0.01, st)
    if xg[-1] < xr[-1] - 1e-9:
        xg = np.r_[xg, xr[-1]]
    # 4. smoothing spline (GCV) - kehalusan 0..10, 5 = otomatis
    w = np.ones_like(xr)
    if awal in ('nol', 'toe'):
        w[0] = 1e4                                       # paksa lewat (0,0)
    # x & y dinormalisasi ke [0,1] supaya skala lambda sama untuk semua data
    x0s, sxs = xr[0], (xr[-1] - xr[0]) or 1.0; sys_ = np.abs(yr).max() or 1.0
    lam = 10 ** (-7.5 + 0.5 * kehalusan)
    try:
        sp = make_smoothing_spline((xr - x0s) / sxs, yr / sys_, w=w, lam=lam)
        yg = sp((xg - x0s) / sxs) * sys_
    except Exception:
        yg = savgol_filter(np.interp(xg, xr, yr), max(5, (len(xg) // 15) | 1), 2)
    # 5. koreksi ML (opsional) + dihaluskan lagi
    if pakai_ml and paket is not None:
        x0n, sx, sy = norm_param(xr, yr)
        F = fitur((xr - x0n) / sx, yr / sy, (xg - x0n) / sx, paket['win'])[paket['kolom']]
        kor = paket['model'].predict(F) * sy
        kor = savgol_filter(kor, max(5, (len(kor) // 10) | 1), 2) if len(kor) > 7 else kor
        yg = yg + kor
    if awal in ('nol', 'toe'):
        yg[0] = 0.0
    yg = np.maximum(yg, 0) if yr.min() >= 0 else yg
    ip = int(np.argmax(yg))
    info.update(F_maks=float(yg[ip]), x_F_maks=float(xg[ip]), x_patah=float(xg[-1]),
                energi=float(np.trapezoid(yg, xg) / 1000 if hasattr(np, 'trapezoid') else np.trapz(yg, xg) / 1000),
                selisih_F_maks=float((yg[ip] - info['F_maks_mentah']) / info['F_maks_mentah'] * 100),
                step=float(st))
    return xg, yg, info


def ke_tabel(xg, yg, satuan_x='mm', satuan_y='N', desimal_x=3, desimal_y=2, tegangan=None):
    """tegangan: None atau dict(A0=mm2, L0=mm) -> keluaran Stress (MPa) - Strain (%)."""
    if tegangan:
        return pd.DataFrame({'Strain (%)': np.round(xg / tegangan['L0'] * 100, desimal_x),
                             'Stress (MPa)': np.round(yg / tegangan['A0'], desimal_y)})
    return pd.DataFrame({f'Elongation ({satuan_x})': np.round(xg * SATUAN_X[satuan_x], desimal_x),
                         f'Force ({satuan_y})': np.round(yg * SATUAN_Y[satuan_y], desimal_y)})


# ----------------------------------------------------------------------------- grafik ekspor (gaya Origin)
WARNA = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948']


def plot_origin(seri, judul='', tampil_mentah=False, dpi=110, warna_tunggal='#C00000'):
    """seri: list of dict(nama, df, x_raw, y_raw). Satu spesimen -> satu garis tegas."""
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 12})
    fig, ax = plt.subplots(figsize=(6.5, 5), dpi=dpi)
    for i, s in enumerate(seri):
        c = warna_tunggal if len(seri) == 1 else WARNA[i % len(WARNA)]
        if tampil_mentah and s.get('x_raw') is not None:
            ax.scatter(s['x_raw'], s['y_raw'], s=6, color='0.65', alpha=.5, lw=0, zorder=1)
        ax.plot(s['df'].iloc[:, 0], s['df'].iloc[:, 1], c=c, lw=2, label=s['nama'], zorder=3)
    df0 = seri[0]['df']
    ax.set_xlabel(df0.columns[0], fontweight='bold'); ax.set_ylabel(df0.columns[1], fontweight='bold')
    if judul:
        ax.set_title(judul, fontweight='bold')
    for sp in ax.spines.values():
        sp.set_linewidth(1.5)
    ax.tick_params(direction='in', width=1.5, length=6, top=True, right=True, labelsize=11)
    ax.minorticks_on(); ax.tick_params(which='minor', direction='in', length=3, top=True, right=True)
    ax.set_xlim(left=0); ax.set_ylim(bottom=0)
    if len(seri) > 1:
        ax.legend(frameon=False, fontsize=10)
    fig.tight_layout()
    return fig


def fig_ke_png(fig, dpi=300):
    buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=dpi); plt.close(fig)
    return buf.getvalue()
