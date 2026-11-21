"""Year-to-year spread: how much a month's value changes from one year to the next, 1981-2010.

For each 0.1-degree square and calendar month, the standard deviation over the 30 years of that month's value
(ERA5-Land monthly means, ~9 km; wind: ERA5 monthly 10 m wind speed, ~25 km). Stored per square:

  tas, d2m      standard deviation in degC (sample, n-1)
  hurs          standard deviation in percentage points of the humidity at the month's mean temperature and dew point
  pr, sf        coefficient of variation (standard deviation / mean): the site's own mean comes from other sources
                (CHELSA precipitation, corrected snowfall), so the spread is applied as a share of that mean
  sfcWind       standard deviation in m/s

and, per 2.5-degree tile, the correlation between every pair of calendar months (66 pairs) of the tile's land-average
anomalies, so the spread of a several-month average (or total) can be worked out in the browser:
  sd(selection) = sqrt(sum_i sum_j rho_ij sd_i sd_j) / k   (an average; for a total, without the / k).

Source data: Copernicus ERA5-Land monthly averaged reanalysis (2m_temperature, 2m_dewpoint_temperature,
total_precipitation, snowfall) and ERA5 monthly averaged reanalysis on single levels (10m_wind_speed), CC BY 4.0,
"Contains modified Copernicus Climate Change Service information". Needs a CDS account (see fetch_era5land_dewpoint.py).

    CDSAPI_RC=<rc> .venv/bin/python scripts/spread_yearly.py fetch      download what is missing (one decade at a time)
    .venv/bin/python scripts/spread_yearly.py build                      -> data/results/spread/yearly.npz

`fetch` keeps disk use low: with --reduce it folds each decade into running sums (data/results/spread/acc-*.npz) and
deletes the download; dew point and snowfall reuse the files already in data/raw.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / 'data/raw/spread'
OUT = ROOT / 'data/results/spread'
DECADES = [(1981, 1990), (1991, 2000), (2001, 2010)]
ROWS, COLS, TILE = 1740, 3600, 25
LAT0, LON0, STEP = 83.99986041515, -180.00013888885002, 0.1
# name: (dataset, CDS variable, NetCDF variable, existing raw file pattern or None)
SOURCES = {
    't2m': ('reanalysis-era5-land-monthly-means', '2m_temperature', 't2m', None),
    'd2m': ('reanalysis-era5-land-monthly-means', '2m_dewpoint_temperature', 'd2m', 'data/raw/era5land-d2m/d2m-{a}-{b}.nc'),
    'tp': ('reanalysis-era5-land-monthly-means', 'total_precipitation', 'tp', None),
    'sf': ('reanalysis-era5-land-monthly-means', 'snowfall', 'sf', 'data/raw/era5land-snow/sf-{a}-{b}.nc'),
    'si10': ('reanalysis-era5-single-levels-monthly-means', '10m_wind_speed', 'si10', None),
}
DAYS = np.array([31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])


def raw_path(name, a, b):
    existing = SOURCES[name][3]
    return ROOT / existing.format(a=a, b=b) if existing else RAW / f'{name}-{a}-{b}.nc'


def fetch(name, a, b):
    import cdsapi
    path = raw_path(name, a, b)
    if path.exists():
        return path
    dataset, variable, _, _ = SOURCES[name]
    request = {'product_type': ['monthly_averaged_reanalysis'], 'variable': [variable], 'year': [str(y) for y in range(a, b + 1)],
               'month': [f'{m:02}' for m in range(1, 13)], 'time': ['00:00'], 'data_format': 'netcdf', 'download_format': 'unarchived'}
    path.parent.mkdir(parents=True, exist_ok=True)
    t = time.time()
    cdsapi.Client(quiet=True).retrieve(dataset, request, str(path) + '.part')
    Path(str(path) + '.part').rename(path)
    print(f'fetched {path.name} in {time.time() - t:.0f} s, {path.stat().st_size / 1e6:.0f} MB', flush=True)
    return path


def square_index(lat, lon):
    """For every square centre, the source grid's (row, col); rows/cols outside the grid are clipped."""
    clat = LAT0 - (np.arange(ROWS) + .5) * STEP
    clon = LON0 + (np.arange(COLS) + .5) * STEP
    dlat, dlon = lat[1] - lat[0], lon[1] - lon[0]
    r = np.clip(np.rint((clat - lat[0]) / dlat).astype(np.int64), 0, len(lat) - 1)
    c = np.rint(((clon - lon[0]) % 360) / dlon).astype(np.int64) % len(lon)
    return r, c


def read(path, var):
    import netCDF4
    with netCDF4.Dataset(path) as ds:
        lat, lon = ds['latitude'][:].data, ds['longitude'][:].data
        times = netCDF4.num2date(ds['valid_time'][:], ds['valid_time'].units)
        v = ds[var]
        for i, t in enumerate(times):
            f = v[i].squeeze() if v.ndim == 4 else v[i]
            yield t.year, t.month, np.ma.filled(f.astype(np.float64), np.nan), lat, lon


def to_squares(field, r, c):
    """Source field -> (ROWS, COLS) at square centres, filling a missing centre from the nearest valued cell within 2."""
    out = field[np.ix_(r, c)]
    if np.isnan(out).any():
        for d in (1, 2):
            for dr in range(-d, d + 1):
                for dc in range(-d, d + 1):
                    if max(abs(dr), abs(dc)) != d: continue
                    alt = field[np.ix_(np.clip(r + dr, 0, field.shape[0] - 1), (c + dc) % field.shape[1])]
                    out = np.where(np.isnan(out), alt, out)
    return out


def humidity_at(dew_c, t_c):
    sat = lambda x: 6.1094 * np.exp(17.625 * x / (x + 243.04))
    return np.minimum(100.0, 100.0 * sat(dew_c) / sat(t_c))


def reduce_all(names):
    """Fold each variable's 30 years into per-square sums (and per-tile yearly land means for correlations)."""
    OUT.mkdir(parents=True, exist_ok=True)
    trow, tcol = np.arange(ROWS) // TILE, np.arange(COLS) // TILE
    nt_r, nt_c = (ROWS + TILE - 1) // TILE, COLS // TILE
    for name in names:
        acc_path = OUT / f'acc-{name}.npz'
        if acc_path.exists():
            print('have', acc_path.name, flush=True); continue
        # Temperature also yields humidity (needs the same year's dew point, already on disk).
        keys = ['t2m', 'hurs'] if name == 't2m' else [name]
        acc = {k: {'s1': np.zeros((12, ROWS, COLS)), 's2': np.zeros((12, ROWS, COLS)), 'n': np.zeros((12, ROWS, COLS), np.uint8),
                   'ty': np.full((30, 12, nt_r, nt_c), np.nan, np.float32)} for k in keys}
        def add(k, year, month, v):
            A, ok = acc[k], np.isfinite(v)
            A['s1'][month - 1][ok] += v[ok]; A['s2'][month - 1][ok] += v[ok] ** 2; A['n'][month - 1][ok] += 1
            w = np.where(ok, v, 0.0)
            sums = np.add.reduceat(np.add.reduceat(w, np.arange(0, ROWS, TILE), axis=0), np.arange(0, COLS, TILE), axis=1)
            cnt = np.add.reduceat(np.add.reduceat(ok.astype(np.float64), np.arange(0, ROWS, TILE), axis=0), np.arange(0, COLS, TILE), axis=1)
            A['ty'][year - 1981, month - 1] = np.where(cnt > 0, sums / np.maximum(cnt, 1), np.nan)
        for a, b in DECADES:
            path = fetch(name, a, b)
            # Dew point read side by side with temperature (both files list the same months in the same order).
            dews = read(raw_path('d2m', a, b), 'd2m') if name == 't2m' else None
            idx = didx = None
            for year, month, field, lat, lon in read(path, SOURCES[name][2]):
                if idx is None: idx = square_index(lat, lon)
                v = to_squares(field, *idx)
                if name in ('t2m', 'd2m'): v = v - 273.15
                elif name in ('tp', 'sf'): v = v * 1000 * DAYS[month - 1]     # m of water per day (monthly mean) -> mm per month
                add(keys[0], year, month, v)
                if dews is not None:
                    dy, dm, dfield, dlat, dlon = next(dews)
                    if (dy, dm) != (year, month): raise ValueError(f'dew point {dy}-{dm} does not match temperature {year}-{month}')
                    if didx is None: didx = square_index(dlat, dlon)
                    with np.errstate(invalid='ignore', over='ignore'): add('hurs', year, month, humidity_at(to_squares(dfield, *didx) - 273.15, v))
            if SOURCES[name][3] is None:
                path.unlink()                                               # our own download: no longer needed
        for k in keys:
            A = acc[k]
            np.savez_compressed(OUT / f'acc-{k}.npz', s1=A['s1'], s2=A['s2'], n=A['n'], tile_year=A['ty'])
            print('reduced', k, flush=True)


def build():
    """acc-*.npz -> data/results/spread/yearly.npz: per-square sd/cv (12, ROWS, COLS) float16 and per-tile rho (66, ...)."""
    out, rho = {}, {}
    pairs = [(i, j) for i in range(12) for j in range(i + 1, 12)]
    prev = np.load(OUT / 'yearly.npz') if (OUT / 'yearly.npz').exists() else None
    def sd_of(name):
        if not (OUT / f'acc-{name}.npz').exists():                 # not fetched yet: stays unknown (the app shows no card)
            print('missing', name, '(left unknown)', flush=True)
            nan = np.full((12, ROWS, COLS), np.nan); return nan, nan, np.full((30, 12, (ROWS + TILE - 1) // TILE, COLS // TILE), np.nan, np.float32)
        d = np.load(OUT / f'acc-{name}.npz'); s1, s2, n = d['s1'], d['s2'], d['n'].astype(np.float64)
        mean = np.where(n >= 25, s1 / np.maximum(n, 1), np.nan)
        var = np.where(n >= 25, (s2 - n * mean ** 2) / np.maximum(n - 1, 1), np.nan)
        return mean, np.sqrt(np.maximum(var, 0)), d['tile_year']
    def corr(tile_year):
        a = tile_year - np.nanmean(tile_year, axis=0)
        r = np.full((66,) + tile_year.shape[2:], np.nan, np.float32)
        for k, (i, j) in enumerate(pairs):
            x, y = a[:, i], a[:, j]; ok = np.isfinite(x) & np.isfinite(y)
            num = np.where(ok, x * y, 0).sum(0); dx = np.sqrt(np.where(ok, x * x, 0).sum(0)); dy = np.sqrt(np.where(ok, y * y, 0).sum(0))
            r[k] = np.where((ok.sum(0) >= 20) & (dx > 0) & (dy > 0), num / np.maximum(dx * dy, 1e-12), np.nan)
        return r
    # A measure whose running sums were removed after an earlier build keeps that build's results (yearly.npz).
    reuse = lambda name, key: prev is not None and not (OUT / f'acc-{name}.npz').exists() and f'sd_{key}' in prev.files and np.isfinite(prev[f'sd_{key}'].astype(np.float32)).any()
    for name, key in (('t2m', 'tas'), ('d2m', 'd2m'), ('hurs', 'hurs'), ('si10', 'sfcWind')):
        if reuse(name, key): out[key], rho[key] = prev[f'sd_{key}'], prev[f'rho_{key}']; print('kept', key, flush=True); continue
        mean, sd, ty = sd_of(name); out[key] = sd.astype(np.float16); rho[key] = corr(ty)
    # A ~9 km grid cell averages out local downpours, so its month-to-month totals vary less than at one place: against
    # 29,722 NOAA GHCN-Daily stations (scripts/check_spread_stations.py) the share read 0.79 of the station's in the
    # tropics and 0.84 elsewhere. The site's precipitation describes the place itself, so the share is scaled by that
    # measured gap (snowfall too, which comes from the same precipitation).
    lat = LAT0 - (np.arange(ROWS) + .5) * STEP
    scale = np.where(np.abs(lat) < 25, 1 / .79, 1 / .84)[None, :, None]
    for name, key in (('tp', 'pr'), ('sf', 'sf')):
        if reuse(name, key): out[key], rho[key] = prev[f'sd_{key}'], prev[f'rho_{key}']; print('kept', key, flush=True); continue
        mean, sd, ty = sd_of(name)
        out[key] = np.where(mean > (1.0 if key == 'pr' else 0.5), sd / np.maximum(mean, 1e-9) * scale, np.nan).astype(np.float16)
        rho[key] = corr(ty)
    out = {k: np.asarray(v) for k, v in out.items()}; rho = {k: np.asarray(v) for k, v in rho.items()}
    np.savez_compressed(OUT / 'yearly.tmp.npz', **{f'sd_{k}': v for k, v in out.items()}, **{f'rho_{k}': v for k, v in rho.items()},
                        meta=json.dumps({'pairs': pairs, 'tile': TILE, 'period': '1981-2010'}))
    (OUT / 'yearly.tmp.npz').replace(OUT / 'yearly.npz')
    print('built', OUT / 'yearly.npz', flush=True)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'fetch': reduce_all([a for a in sys.argv[2:] if not a.startswith('-')] or list(SOURCES))
    elif cmd == 'build': build()
