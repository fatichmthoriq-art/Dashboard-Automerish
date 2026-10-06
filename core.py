"""Fungsi inti aplikasi: baca data UTM, fitur model, rapikan(), dan plot gaya Origin.
Harus identik dengan notebook pelatihan agar model memberi hasil yang sama."""
import io
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.signal import savgol_filter

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


SATUAN_X = {'mm': 1.0, 'cm': 0.1, 'm': 1e-3, 'in': 1 / 25.4}
SATUAN_Y = {'N': 1.0, 'kN': 1e-3, 'kgf': 1 / 9.80665, 'lbf': 0.224809}


def step_otomatis(rentang, n=200):
    kasar = rentang / n; e = 10 ** np.floor(np.log10(kasar))
    return min([1, 2, 2.5, 5, 10], key=lambda m: abs(m * e - kasar)) * e


def titik_patah(xr, yr, frac):
    ys = savgol_filter(yr, max(5, (len(yr) // 25) | 1), 2) if len(yr) > 7 else yr
    ip = int(np.argmax(ys)); turun = np.where(ys[ip:] < frac * ys[ip])[0]
    return xr[ip + turun[0]] if len(turun) else xr[-1]


def rapikan(x_raw, y_raw, paket, step=None, mulai_nol=None, potong=True, potong_frac=None,
            x_akhir=None, satuan_x='mm', satuan_y='N', desimal_x=None, desimal_y=None,
            pakai_ml=True):
    A = paket['aturan']
    xr, yr = bersihkan(np.asarray(x_raw, float), np.asarray(y_raw, float))
    if len(xr) < 5:
        raise ValueError('data terlalu sedikit (< 5 titik)')
    x0, sx, sy = norm_param(xr, yr)
    mulai_nol = A.get('mulai_nol', True) if mulai_nol is None else mulai_nol
    if step in (None, 'auto'):
        s = A.get('step', 'auto')
        step = step_otomatis(sx) if s in ('auto', None) or not A.get('interval_seragam', True) else float(s)
    a = 0.0 if mulai_nol else xr[0]
    b = xr[-1]
    frac = potong_frac if potong_frac is not None else A.get('potong_frac')
    if x_akhir:
        b = x_akhir
    elif potong and frac:
        b = titik_patah(xr, yr, frac)
    xq = np.arange(a, b + step * 0.5, step)
    F = fitur((xr - x0) / sx, yr / sy, (xq - x0) / sx, paket['win'])[paket['kolom']]
    koreksi = paket['model'].predict(F) if pakai_ml else 0.0
    yq = (F['interp'].to_numpy() + koreksi) * sy
    if mulai_nol and abs(xq[0]) < 1e-12:
        yq[0] = 0.0
    dx = A.get('desimal_x', 3) if desimal_x is None else desimal_x
    dy = A.get('desimal_y', 2) if desimal_y is None else desimal_y
    xq = xq * SATUAN_X[satuan_x]; yq = yq * SATUAN_Y[satuan_y]
    return pd.DataFrame({f'Elongation ({satuan_x})': np.round(xq, dx),
                         f'Force ({satuan_y})': np.round(yq, dy)})


def ringkasan(df):
    x, y = df.iloc[:, 0].to_numpy(), df.iloc[:, 1].to_numpy()
    ip = int(np.argmax(y))
    return {'F maks': y[ip], 'Elongation saat F maks': x[ip], 'Elongation akhir': x[-1], 'Jumlah titik': len(df)}


# ----------------------------------------------------------------------------- grafik
WARNA = ['#C00000', '#1F4E79', '#2E7D32', '#E07B00', '#6A1B9A', '#00838F', '#5D4037', '#AD1457']


def _gaya_origin(ax):
    for s in ax.spines.values():
        s.set_linewidth(1.5)
    ax.tick_params(direction='in', width=1.5, length=6, top=True, right=True, labelsize=11)
    ax.minorticks_on()
    ax.tick_params(which='minor', direction='in', length=3, top=True, right=True)


def plot_origin(seri, judul='', tampil_mentah=True, dpi=110):
    """seri: list of dict(nama, df, x_raw, y_raw)."""
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 12})
    fig, ax = plt.subplots(figsize=(6.5, 5), dpi=dpi)
    for i, s in enumerate(seri):
        c = WARNA[i % len(WARNA)]
        if tampil_mentah and s.get('x_raw') is not None:
            ax.scatter(s['x_raw'], s['y_raw'], s=9, facecolors='none', edgecolors=c, alpha=.35, lw=.8)
        ax.plot(s['df'].iloc[:, 0], s['df'].iloc[:, 1], c=c, lw=2, label=s['nama'])
    df0 = seri[0]['df']
    ax.set_xlabel(df0.columns[0], fontweight='bold'); ax.set_ylabel(df0.columns[1], fontweight='bold')
    if judul:
        ax.set_title(judul, fontweight='bold')
    _gaya_origin(ax)
    ax.set_xlim(left=0); ax.set_ylim(bottom=0)
    ax.legend(frameon=False, fontsize=10)
    fig.tight_layout()
    return fig


def fig_ke_png(fig, dpi=300):
    buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=dpi); plt.close(fig)
    return buf.getvalue()
