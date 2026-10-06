"""Digitasi gambar grafik (pengganti klik manual di Automeris/WebPlotDigitizer).
1. cari bingkai/sumbu, 2. kenali warna kurva, 3. baca angka sumbu (OCR Tesseract, bisa dikoreksi),
4. ambil titik kurva per warna -> data (x, y)."""
import re

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

try:
    import pytesseract
    pytesseract.get_tesseract_version()
    OCR_ADA = True
except Exception:
    OCR_ADA = False


def muat(file_or_bytes):
    img = Image.open(file_or_bytes).convert('RGB')
    if max(img.size) < 900:                          # gambar kecil diperbesar supaya OCR & ekstraksi stabil
        f = 900 / max(img.size)
        img = img.resize((int(img.width * f), int(img.height * f)), Image.LANCZOS)
    return np.array(img)


# ----------------------------------------------------------------------------- bingkai
def _maxrun(b):
    out = np.zeros(b.shape[0], int)
    for i, r in enumerate(b):
        if r.any():
            d = np.diff(np.concatenate([[0], r.view(np.int8), [0]]))
            out[i] = (np.where(d == -1)[0] - np.where(d == 1)[0]).max()
    return out


def cari_bingkai(rgb):
    gelap = rgb.mean(2) < 110
    H, W = gelap.shape
    rh, rv = _maxrun(gelap), _maxrun(gelap.T)
    baris, kol = np.where(rh > 0.35 * W)[0], np.where(rv > 0.35 * H)[0]
    if len(baris) == 0 or len(kol) == 0:
        raise ValueError('Sumbu/bingkai grafik tidak ditemukan. Pastikan gambar berisi grafik dengan garis sumbu.')
    bawah, kiri = baris.max(), kol.min()
    atas = baris.min() if baris.min() < bawah - 0.2 * H else 0
    kanan = kol.max() if kol.max() > kiri + 0.2 * W else W - 1
    return int(atas), int(bawah), int(kiri), int(kanan)


# ----------------------------------------------------------------------------- warna kurva
def _hue(sub):
    r, g, b = sub[..., 0], sub[..., 1], sub[..., 2]
    return (np.degrees(np.arctan2(np.sqrt(3) * (g - b), 2 * r - g - b)) + 360) % 360


def _interior(rgb, bk):
    atas, bawah, kiri, kanan = bk
    m = max(3, int(0.006 * max(rgb.shape[:2])))
    return rgb[atas + m:bawah - m + 1, kiri + m:kanan - m + 1].astype(float), (atas + m, kiri + m)


def kandidat_warna(rgb, bk, maks=6):
    """Daftar warna garis di dalam area plot: [{'id','nama','rgb','n'}] urut dari yang terbanyak."""
    sub, _ = _interior(rgb, bk)
    mx, mn = sub.max(2), sub.min(2)
    sat = (mx - mn) / (mx + 1e-6)
    out = []
    gelap = (mx < 110) & (sat < 0.35)
    if gelap.sum() > 0.0008 * gelap.size:
        out.append(dict(id='hitam', nama='Hitam / gelap', rgb=(30, 30, 30), n=int(gelap.sum())))
    berwarna = (sat > 0.30) & (mx > 60)
    if berwarna.sum():
        h = _hue(sub)[berwarna]
        hist, ed = np.histogram(h, 36, (0, 360))
        sudah = np.zeros(36, bool)
        for k in np.argsort(hist)[::-1]:
            if hist[k] < 0.0006 * berwarna.size or sudah[k] or len(out) >= maks:
                continue
            sudah[[(k - 1) % 36, k, (k + 1) % 36]] = True
            pusat = (ed[k] + 5) % 360
            sel = berwarna & (np.abs((_hue(sub) - pusat + 180) % 360 - 180) < 15)
            nama = _nama_warna(pusat)
            pekat = sel & (sat >= 0.85)
            muda = sel & (sat < 0.75) & ~ndi.binary_dilation(pekat, iterations=3)
            if pekat.sum() > 0.15 * sel.sum() and muda.sum() > 0.10 * sel.sum():
                # warna sama tapi dua intensitas (mis. garis pekat + titik transparan) -> pisahkan
                for lbl, mk, rng in [('pekat', pekat, (0.85, 1.01)), ('muda/transparan', muda, (0.25, 0.75))]:
                    c = tuple(int(v) for v in np.median(sub[mk], axis=0))
                    out.append(dict(id=f'h{int(pusat)}{lbl[:2]}', nama=f'{nama} {lbl}', rgb=c, n=int(mk.sum()),
                                    hue=pusat, sat=rng, buang_pekat=lbl != 'pekat'))
            else:
                c = tuple(int(v) for v in np.median(sub[sel], axis=0))
                out.append(dict(id=f'h{int(pusat)}', nama=nama, rgb=c, n=int(sel.sum()), hue=pusat))
    return sorted(out, key=lambda d: -d['n'])


def _nama_warna(h):
    for batas, n in [(15, 'Merah'), (45, 'Oranye'), (70, 'Kuning'), (160, 'Hijau'), (200, 'Toska'),
                     (255, 'Biru'), (290, 'Ungu'), (340, 'Magenta'), (361, 'Merah')]:
        if h < batas:
            return n
    return 'Warna'


def ekstrak(rgb, bk, warna, mode='garis'):
    """Ambil piksel kurva untuk satu warna -> (px, py) satu titik per kolom piksel."""
    sub, (oy, ox) = _interior(rgb, bk)
    mx, mn = sub.max(2), sub.min(2)
    sat = (mx - mn) / (mx + 1e-6)
    if warna['id'] == 'hitam':
        mask = (mx < 110) & (sat < 0.35)
    else:
        hue_ok = np.abs((_hue(sub) - warna['hue'] + 180) % 360 - 180) < 18
        lo, hi = warna.get('sat', (0.25, 1.01))
        mask = (sat >= lo) & (sat < hi) & (mx > 50) & hue_ok
        if warna.get('buang_pekat'):
            mask &= ~ndi.binary_dilation((sat >= 0.85) & hue_ok, iterations=3)
    lab, n = ndi.label(mask, np.ones((3, 3)))
    if n == 0:
        raise ValueError('Kurva dengan warna ini tidak ditemukan')
    sl = ndi.find_objects(lab)
    lebar = np.array([s[1].stop - s[1].start for s in sl]); tinggi = np.array([s[0].stop - s[0].start for s in sl])
    Wi, Hi = mask.shape[1], mask.shape[0]
    if mode == 'garis':
        # buang teks, tick, kotak legenda: simpan komponen yang lebar/tinggi
        simpan = [i for i in range(n) if lebar[i] > 0.12 * Wi or tinggi[i] > 0.25 * Hi]
        if not simpan:
            simpan = [int(lebar.argmax())]
    else:   # titik/marker: buang komponen sangat besar (teks panjang tetap kecil)
        simpan = [i for i in range(n) if lebar[i] < 0.08 * Wi and tinggi[i] < 0.08 * Hi]
    mask = np.isin(lab, [i + 1 for i in simpan])
    cols = np.where(mask.any(0))[0]
    if mode != 'garis':
        py = np.array([np.median(np.where(mask[:, c])[0]) for c in cols])
        return cols + ox, py + oy
    return _lacak(mask, cols, ox, oy)


def _segmen(kol):
    r = np.where(kol)[0]
    if len(r) == 0:
        return []
    putus = np.where(np.diff(r) > 2)[0]
    awal = np.r_[r[0], r[putus + 1]]; akhir = np.r_[r[putus], r[-1]]
    return [((a + b) / 2, b - a + 1) for a, b in zip(awal, akhir)]


def _lacak(mask, cols, ox, oy):
    # Telusuri garis kolom demi kolom: pilih segmen terdekat dengan posisi sebelumnya.
    # Mencegah garis 'melompat' ke titik/marker lain yang warnanya sama.
    seg = {c: _segmen(mask[:, c]) for c in cols}
    tunggal = [c for c in cols if len(seg[c]) == 1]
    mulai = tunggal[0] if tunggal else cols[0]
    hasil = {}
    for arah in (1, -1):
        prev = seg[mulai][0][0] if seg[mulai] else None
        urut = [c for c in cols if (c >= mulai if arah == 1 else c < mulai)]
        urut = urut if arah == 1 else urut[::-1]
        for c in urut:
            if not seg[c]:
                continue
            pusat = min(seg[c], key=lambda t: abs(t[0] - prev)) if prev is not None else seg[c][0]
            hasil[c] = pusat[0]; prev = pusat[0]
    cs = np.array(sorted(hasil)); py = np.array([hasil[c] for c in cs])
    return cs + ox, py + oy


# ----------------------------------------------------------------------------- OCR sumbu
def _angka(t):
    t = t.strip().replace(',', '.').replace('O', '0').replace('o', '0').replace('−', '-').replace('—', '-')
    return float(t) if re.fullmatch(r'-?\d+(\.\d+)?', t) else None


def _ocr(potong, ox, oy, skala=3):
    if potong.size == 0:
        return []
    im = Image.fromarray(potong.astype(np.uint8)).convert('L')
    im = im.resize((im.width * skala, im.height * skala), Image.LANCZOS)
    d = pytesseract.image_to_data(im, config='--psm 11 -c tessedit_char_whitelist=0123456789.,-',
                                  output_type=pytesseract.Output.DICT)
    out = []
    for i, t in enumerate(d['text']):
        v = _angka(t or '')
        if v is None or float(d['conf'][i]) < 30:
            continue
        cx = (d['left'][i] + d['width'][i] / 2) / skala + ox
        cy = (d['top'][i] + d['height'][i] / 2) / skala + oy
        out.append((cx, cy, v))
    return out


def _fit(pix, val):
    pix, val = np.asarray(pix, float), np.asarray(val, float)
    if len(pix) < 2:
        return None
    best = None
    for i in range(len(pix)):
        for j in range(i + 1, len(pix)):
            if pix[i] == pix[j] or val[i] == val[j]:
                continue
            a = (val[j] - val[i]) / (pix[j] - pix[i]); b = val[i] - a * pix[i]
            inl = np.abs(a * pix + b - val) < 0.02 * (np.ptp(val) or 1)
            if best is None or inl.sum() > best.sum():
                best = inl
    if best is None or best.sum() < 2:
        return None
    a, b = np.polyfit(pix[best], val[best], 1)
    return float(a), float(b), int(best.sum())


def baca_sumbu(rgb, bk):
    """Tebak nilai sumbu di tepi bingkai: dict(x_kiri, x_kanan, y_bawah, y_atas, n_x, n_y) atau None."""
    if not OCR_ADA:
        return None
    atas, bawah, kiri, kanan = bk
    H, W = rgb.shape[:2]
    x0, x1 = max(0, kiri - int(.06 * W)), min(W, kanan + int(.06 * W))
    xs = [(cx, v) for cx, cy, v in _ocr(rgb[bawah + 3:min(H, bawah + int(.10 * H)), x0:x1], x0, bawah + 3)]
    a0, a1 = max(0, atas - int(.03 * H)), min(H, bawah + int(.03 * H))
    c0 = max(0, kiri - int(.16 * W))
    ys = [(cy, v) for cx, cy, v in _ocr(rgb[a0:a1, c0:max(c0 + 1, kiri - 3)], c0, a0)]
    fx = _fit(*zip(*xs)) if len(xs) >= 2 else None
    fy = _fit(*zip(*ys)) if len(ys) >= 2 else None
    if fx is None or fy is None:
        return None
    r = lambda v: float(np.round(v, 6))
    return dict(x_kiri=r(fx[0] * kiri + fx[1]), x_kanan=r(fx[0] * kanan + fx[1]),
                y_bawah=r(fy[0] * bawah + fy[1]), y_atas=r(fy[0] * atas + fy[1]), n_x=fx[2], n_y=fy[2])


def ke_data(px, py, bk, x_kiri, x_kanan, y_bawah, y_atas):
    atas, bawah, kiri, kanan = bk
    x = x_kiri + (px - kiri) / (kanan - kiri) * (x_kanan - x_kiri)
    y = y_bawah + (bawah - py) / (bawah - atas) * (y_atas - y_bawah)
    return x, y
