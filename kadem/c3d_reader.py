"""Bağımsız C3D okuyucu (yalnızca numpy).

C3D standardına göre başlık, parametre ve veri bölümlerini okur.
Intel, DEC ve MIPS işlemci biçimlerini; float ve tamsayı veri depolamasını destekler.

Zaman kuralı (Vicon/ezc3d ile aynı): 1 tabanlı kare numarası F, t = (F - 1) / hız saniyesine karşılık gelir.
Dizideki 0. örnek, başlıktaki ilk kareye (first_frame) aittir; yani i. örneğin zamanı
(first_frame - 1 + i) / hız'dır.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import numpy as np

PROC_INTEL, PROC_DEC, PROC_MIPS = 84, 85, 86


class C3DError(Exception):
    """C3D dosyası okunamadığında."""


@dataclass
class Param:
    group: str
    name: str
    dtype: int          # -1 char, 1 byte, 2 int16, 4 float
    dims: tuple
    raw: bytes
    desc: str = ''
    _proc: int = PROC_INTEL

    # --- dönüştürücüler -------------------------------------------------
    def _np(self, kind: str):
        n = int(np.prod(self.dims)) if self.dims else 1
        if kind == 'i2':
            dt = '>i2' if self._proc == PROC_MIPS else '<i2'
            return np.frombuffer(self.raw, dtype=dt, count=n).astype(np.int64)
        if kind == 'u2':
            dt = '>u2' if self._proc == PROC_MIPS else '<u2'
            return np.frombuffer(self.raw, dtype=dt, count=n).astype(np.int64)
        if kind == 'f4':
            return _floats(self.raw[:4 * n], self._proc).astype(np.float64)
        if kind == 'u1':
            return np.frombuffer(self.raw, dtype='u1', count=n).astype(np.int64)
        raise ValueError(kind)

    @property
    def value(self):
        """Parametre değeri: metinler için str/list[str], sayılar için skaler ya da numpy dizisi."""
        if self.dtype == -1:
            return self.strings if len(self.dims) >= 2 else self.raw.decode('latin-1').rstrip(' \x00')
        kind = {1: 'u1', 2: 'i2', 4: 'f4'}.get(self.dtype)
        if kind is None:
            return None
        arr = self._np(kind)
        if not self.dims:
            return arr[0] if arr.size else None
        arr = arr.reshape(self.dims, order='F')
        return arr

    @property
    def strings(self) -> list:
        if self.dtype != -1:
            return []
        if not self.dims:
            return [self.raw.decode('latin-1').rstrip(' \x00')]
        ln = self.dims[0]
        n = int(np.prod(self.dims[1:])) if len(self.dims) > 1 else 1
        out = []
        for i in range(n):
            s = self.raw[i * ln:(i + 1) * ln].decode('latin-1')
            out.append(s.rstrip(' \x00').strip())
        return out

    @property
    def floats(self) -> np.ndarray:
        if self.dtype == 4:
            return self._np('f4')
        if self.dtype == 2:
            return self._np('i2').astype(float)
        if self.dtype == 1:
            return self._np('u1').astype(float)
        return np.array([], float)

    @property
    def ints(self) -> np.ndarray:
        if self.dtype == 2:
            return self._np('i2')
        if self.dtype == 1:
            return self._np('u1')
        if self.dtype == 4:
            return np.round(self._np('f4')).astype(np.int64)
        return np.array([], np.int64)

    @property
    def uints(self) -> np.ndarray:
        if self.dtype == 2:
            return self._np('u2')
        return self.ints


def _floats(buf: bytes, proc: int) -> np.ndarray:
    if proc == PROC_MIPS:
        return np.frombuffer(buf, dtype='>f4').astype(np.float32)
    if proc == PROC_DEC:
        b = np.frombuffer(buf, dtype='u1').reshape(-1, 4)[:, [2, 3, 0, 1]].copy()
        return (b.view('<f4').reshape(-1) / 4.0).astype(np.float32)
    return np.frombuffer(buf, dtype='<f4')


@dataclass
class Event:
    context: str      # 'Left', 'Right', 'General' ...
    label: str        # 'Foot Strike', 'Foot Off', ...
    time: float       # saniye
    subject: str = ''
    description: str = ''
    icon_id: int = 0


@dataclass
class C3DFile:
    path: str
    proc: int
    point_rate: float
    analog_rate: float
    first_frame: int          # 1 tabanlı (Vicon kare numarası)
    n_frames: int
    point_scale: float
    point_labels: list        # önek temizlenmiş
    point_labels_raw: list
    points: np.ndarray        # (n_frames, n_points, 3), geçersiz -> NaN
    residuals: np.ndarray     # (n_frames, n_points), geçersiz -> -1
    analog_labels: list
    analog_units: list
    analog: np.ndarray        # (n_samples, n_channels), ölçeklenmiş
    analog_spf: int           # kare başına analog örnek
    events: list
    params: dict = field(repr=False, default_factory=dict)
    groups: dict = field(repr=False, default_factory=dict)
    label_prefix: str = ''
    warnings: list = field(default_factory=list)

    # ------------------------------------------------------------------
    def get(self, group: str, name: str, default=None):
        p = self.params.get((group.upper(), name.upper()))
        return default if p is None else p.value

    def param(self, group: str, name: str):
        return self.params.get((group.upper(), name.upper()))

    def has_group(self, group: str) -> bool:
        return group.upper() in self.groups

    def group_params(self, group: str) -> dict:
        g = group.upper()
        return {n: p for (gg, n), p in self.params.items() if gg == g}

    @property
    def first_frame0(self) -> int:
        """0 tabanlı ilk kare (ezc3d 'first_frame' ile aynı)."""
        return self.first_frame - 1

    @property
    def t0(self) -> float:
        """Dizideki ilk kare örneğinin zamanı (s)."""
        return self.first_frame0 / self.point_rate

    @property
    def analog_t0(self) -> float:
        return self.first_frame0 / self.point_rate

    def point_index(self, label: str):
        try:
            return self.point_labels.index(label)
        except ValueError:
            return None

    def point_times(self) -> np.ndarray:
        return (self.first_frame0 + np.arange(self.n_frames)) / self.point_rate

    def analog_times(self) -> np.ndarray:
        n = self.analog.shape[0]
        return self.analog_t0 + np.arange(n) / self.analog_rate if n else np.array([])


def _concat_labels(params: dict, group: str, base: str) -> list:
    """LABELS, LABELS2, LABELS3 ... birleştirir."""
    out = []
    p = params.get((group, base))
    if p is not None:
        out.extend(p.strings if p.dtype == -1 else [])
    k = 2
    while (group, f'{base}{k}') in params:
        p2 = params[(group, f'{base}{k}')]
        out.extend(p2.strings if p2.dtype == -1 else [])
        k += 1
    return out


def _concat_floats(params: dict, group: str, base: str) -> np.ndarray:
    parts = []
    p = params.get((group, base))
    if p is not None:
        parts.append(p.floats)
    k = 2
    while (group, f'{base}{k}') in params:
        parts.append(params[(group, f'{base}{k}')].floats)
        k += 1
    return np.concatenate(parts) if parts else np.array([], float)


def _concat_ints(params: dict, group: str, base: str, unsigned=False) -> np.ndarray:
    parts = []
    p = params.get((group, base))
    if p is not None:
        parts.append(p.uints if unsigned else p.ints)
    k = 2
    while (group, f'{base}{k}') in params:
        q = params[(group, f'{base}{k}')]
        parts.append(q.uints if unsigned else q.ints)
        k += 1
    return np.concatenate(parts) if parts else np.array([], np.int64)


def _parse_params(buf: bytes, start: int, proc: int):
    params, groups = {}, {}
    gid_name = {}
    i16 = '>i2' if proc == PROC_MIPS else '<i2'
    pos = start + 4
    pending = []  # (group_id, Param) -> grup adı sonra bulunabilir
    n = len(buf)
    while pos < n - 2:
        nchar = np.frombuffer(buf, 'i1', 1, pos)[0]
        if nchar == 0:
            break
        gid = int(np.frombuffer(buf, 'i1', 1, pos + 1)[0])
        ln = abs(int(nchar))
        name = buf[pos + 2:pos + 2 + ln].decode('latin-1').strip().upper()
        off_pos = pos + 2 + ln
        offset = int(np.frombuffer(buf, i16, 1, off_pos)[0])
        p = off_pos + 2
        if gid < 0:
            dl = buf[p]
            desc = buf[p + 1:p + 1 + dl].decode('latin-1', 'replace').strip()
            gid_name[-gid] = name
            groups[name] = desc
        else:
            dtype = int(np.frombuffer(buf, 'i1', 1, p)[0])
            nd = buf[p + 1]
            dims = tuple(int(d) for d in buf[p + 2:p + 2 + nd])
            p2 = p + 2 + nd
            nbytes = abs(dtype) * (int(np.prod(dims)) if nd else 1)
            raw = bytes(buf[p2:p2 + nbytes])
            p3 = p2 + nbytes
            dl = buf[p3] if p3 < n else 0
            desc = buf[p3 + 1:p3 + 1 + dl].decode('latin-1', 'replace').strip() if p3 < n else ''
            pending.append((gid, Param('', name, dtype, dims, raw, desc, proc)))
        if offset == 0:
            break
        pos = off_pos + offset
    for gid, prm in pending:
        g = gid_name.get(gid, f'GROUP{gid}')
        prm.group = g
        params[(g, prm.name)] = prm
    return params, groups


def read_c3d(path: str, read_analog: bool = True) -> C3DFile:
    with open(path, 'rb') as fh:
        buf = fh.read()
    if len(buf) < 1024:
        raise C3DError('Dosya çok kısa, C3D değil.')
    pblock = buf[0]
    if buf[1] != 0x50:
        raise C3DError('C3D anahtar baytı (0x50) yok, dosya C3D değil.')
    pstart = (pblock - 1) * 512
    proc = buf[pstart + 3]
    if proc not in (PROC_INTEL, PROC_DEC, PROC_MIPS):
        proc = PROC_INTEL
    u2 = '>u2' if proc == PROC_MIPS else '<u2'
    hw = np.frombuffer(buf, u2, 12, 0).astype(np.int64)
    n_points = int(hw[1])
    n_analog_total = int(hw[2])
    first = int(hw[3])
    last = int(hw[4])
    scale = float(_floats(buf[12:16], proc)[0])
    data_start = int(hw[8])
    spf = int(hw[9])
    rate = float(_floats(buf[20:24], proc)[0])

    params, groups = _parse_params(buf, pstart, proc)
    warnings = []

    def P(g, n):
        return params.get((g, n))

    # --- temel sayılar (parametreler başlıktan önceliklidir) -------------
    if P('POINT', 'USED') is not None:
        pu = int(P('POINT', 'USED').uints[0])
        if pu != n_points:
            warnings.append(f'POINT:USED ({pu}) başlıktaki nokta sayısından ({n_points}) farklı; başlık kullanıldı.')
    if P('POINT', 'RATE') is not None:
        r = float(P('POINT', 'RATE').floats[0])
        if r > 0:
            rate = r
    if P('POINT', 'SCALE') is not None:
        scale = float(P('POINT', 'SCALE').floats[0])
    if P('POINT', 'DATA_START') is not None:
        ds = int(P('POINT', 'DATA_START').uints[0])
        if ds > 0:
            data_start = ds
    # İlk kare: TRIAL:ACTUAL_START_FIELD (2 x 16 bit) varsa onu kullan (65535 üzeri kareler)
    if P('TRIAL', 'ACTUAL_START_FIELD') is not None:
        v = P('TRIAL', 'ACTUAL_START_FIELD').uints
        if v.size >= 2:
            fs_ = int(v[0] + 65536 * v[1])
            if fs_ > 0:
                first = fs_
    n_frames = last - first + 1
    if P('TRIAL', 'ACTUAL_END_FIELD') is not None:
        v = P('TRIAL', 'ACTUAL_END_FIELD').uints
        if v.size >= 2:
            le = int(v[0] + 65536 * v[1])
            if le >= first:
                n_frames = le - first + 1
    if n_frames <= 0 and P('POINT', 'FRAMES') is not None:
        fr = P('POINT', 'FRAMES')
        n_frames = int(fr.floats[0]) if fr.dtype == 4 else int(fr.uints[0])

    is_float = scale < 0
    wbytes = 4 if is_float else 2
    if spf <= 0:
        spf = 1
    n_ch = n_analog_total // spf if spf else 0
    if P('ANALOG', 'USED') is not None:
        au = int(P('ANALOG', 'USED').uints[0])
        if au and au != n_ch and spf:
            warnings.append(f'ANALOG:USED ({au}) ile başlıktaki kanal sayısı ({n_ch}) farklı; başlık kullanıldı.')
    analog_rate = rate * spf
    if P('ANALOG', 'RATE') is not None:
        ar = float(P('ANALOG', 'RATE').floats[0])
        if ar > 0 and abs(ar - analog_rate) > 1e-3 and n_ch:
            warnings.append(f'ANALOG:RATE ({ar}) ile kare hızı × örnek ({analog_rate}) farklı; {analog_rate} kullanıldı.')

    frame_words = 4 * n_points + n_analog_total
    frame_bytes = frame_words * wbytes
    dpos = (data_start - 1) * 512
    avail = (len(buf) - dpos) // frame_bytes if frame_bytes else 0
    if n_frames > avail:
        warnings.append(f'Dosyada {n_frames} kare bekleniyordu, {avail} kare okunabildi.')
        n_frames = int(avail)

    raw = np.frombuffer(buf, dtype='u1', count=n_frames * frame_bytes, offset=dpos)
    raw = raw.reshape(n_frames, frame_bytes)
    pbytes = 4 * n_points * wbytes

    # --- noktalar ---------------------------------------------------------
    if n_points:
        pr = raw[:, :pbytes].reshape(-1)
        if is_float:
            vals = _floats(pr.tobytes(), proc).astype(np.float64).reshape(n_frames, n_points, 4)
            last_word = np.where(np.isfinite(vals[:, :, 3]), vals[:, :, 3], -1).astype(np.int64)
            xyz = vals[:, :, :3].copy()
        else:
            i2 = '>i2' if proc == PROC_MIPS else '<i2'
            vals = np.frombuffer(pr.tobytes(), dtype=i2).astype(np.float64).reshape(n_frames, n_points, 4)
            last_word = vals[:, :, 3].astype(np.int64)
            xyz = vals[:, :, :3] * abs(scale)
        invalid = (last_word < 0) | ~np.isfinite(xyz).all(axis=2)
        resid = (last_word & 0xff).astype(np.float64) * abs(scale)
        resid[invalid] = -1.0
        xyz[invalid] = np.nan
    else:
        xyz = np.zeros((n_frames, 0, 3))
        resid = np.zeros((n_frames, 0))

    # --- analog -------------------------------------------------------------
    labels_raw = _concat_labels(params, 'POINT', 'LABELS')[:n_points]
    while len(labels_raw) < n_points:
        labels_raw.append(f'Nokta{len(labels_raw) + 1}')
    a_labels = _concat_labels(params, 'ANALOG', 'LABELS')[:n_ch]
    while len(a_labels) < n_ch:
        a_labels.append(f'Kanal{len(a_labels) + 1}')
    a_units = _concat_labels(params, 'ANALOG', 'UNITS')[:n_ch]
    while len(a_units) < n_ch:
        a_units.append('')

    if read_analog and n_ch:
        ar_ = raw[:, pbytes:].reshape(-1)
        fmt = P('ANALOG', 'FORMAT')
        unsigned = fmt is not None and fmt.dtype == -1 and str(fmt.value).upper().startswith('UNSIGNED')
        if is_float:
            av = _floats(ar_.tobytes(), proc).astype(np.float64)
        else:
            if unsigned:
                dt = '>u2' if proc == PROC_MIPS else '<u2'
            else:
                dt = '>i2' if proc == PROC_MIPS else '<i2'
            av = np.frombuffer(ar_.tobytes(), dtype=dt).astype(np.float64)
        av = av.reshape(n_frames * spf, n_ch)
        gen = float(P('ANALOG', 'GEN_SCALE').floats[0]) if P('ANALOG', 'GEN_SCALE') is not None else 1.0
        sc = _concat_floats(params, 'ANALOG', 'SCALE')
        off = _concat_ints(params, 'ANALOG', 'OFFSET', unsigned=unsigned).astype(np.float64)
        scv = np.ones(n_ch)
        ofv = np.zeros(n_ch)
        scv[:min(n_ch, sc.size)] = sc[:n_ch]
        ofv[:min(n_ch, off.size)] = off[:n_ch]
        analog = (av - ofv[None, :]) * (scv[None, :] * gen)
    else:
        analog = np.zeros((0, n_ch))

    # --- etiket önekleri -------------------------------------------------------
    prefix = ''
    pref = P('SUBJECTS', 'LABEL_PREFIXES')
    if pref is not None and pref.dtype == -1:
        pl = [s for s in pref.strings if s]
        if len(pl) == 1:
            prefix = pl[0]
    labels = []
    for s in labels_raw:
        if prefix and s.startswith(prefix):
            s = s[len(prefix):]
        elif ':' in s:
            s = s.split(':', 1)[1]
        labels.append(s.strip())

    # --- event'ler ---------------------------------------------------------------
    events = []
    if P('EVENT', 'LABELS') is not None and P('EVENT', 'TIMES') is not None:
        lab = P('EVENT', 'LABELS').strings
        ctx = P('EVENT', 'CONTEXTS').strings if P('EVENT', 'CONTEXTS') is not None else [''] * len(lab)
        tp = P('EVENT', 'TIMES')
        tv = tp.floats
        if len(tp.dims) >= 2 and tp.dims[0] == 2:
            tv = tv.reshape(tp.dims, order='F')
            times = tv[0] * 60.0 + tv[1]
        else:
            times = tv
        subj = P('EVENT', 'SUBJECTS').strings if P('EVENT', 'SUBJECTS') is not None else []
        desc = P('EVENT', 'DESCRIPTIONS').strings if P('EVENT', 'DESCRIPTIONS') is not None else []
        icon = P('EVENT', 'ICON_IDS').ints if P('EVENT', 'ICON_IDS') is not None else []
        used = len(lab)
        if P('EVENT', 'USED') is not None:
            used = min(used, int(P('EVENT', 'USED').uints[0]))
        for k in range(min(used, len(times))):
            events.append(Event(context=(ctx[k] if k < len(ctx) else ''), label=lab[k], time=float(times[k]),
                                subject=(subj[k] if k < len(subj) else ''),
                                description=(desc[k] if k < len(desc) else ''),
                                icon_id=int(icon[k]) if k < len(icon) else 0))
        events.sort(key=lambda e: e.time)

    return C3DFile(path=os.path.abspath(path), proc=proc, point_rate=rate, analog_rate=analog_rate,
                   first_frame=first, n_frames=int(n_frames), point_scale=scale,
                   point_labels=labels, point_labels_raw=labels_raw, points=xyz, residuals=resid,
                   analog_labels=a_labels, analog_units=a_units, analog=analog, analog_spf=spf,
                   events=events, params=params, groups=groups, label_prefix=prefix, warnings=warnings)
