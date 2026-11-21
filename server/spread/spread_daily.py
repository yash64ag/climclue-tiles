"""Day-to-day spread: how far a single day usually strays from its month's normal.

For each 0.1-degree square and calendar month, the standard deviation of the daily values around that calendar month's
mean over a 10-year sample of 1981-2010 (every third year: 1981, 1984, ... 2008), for the daily mean, the daily maximum
(day high) and the daily minimum (night low) of 2 m temperature. Ten years give about 300 days per calendar month,
plenty for a stable spread. From the same days it also stores the year-to-year spread of the monthly average day high
and night low (10 years; the 30-year monthly data has no daily highs or lows).

Source: Copernicus ERA5-Land post-processed daily statistics (derived-era5-land-daily-statistics, ~9 km), UTC days,
CC BY 4.0, "Contains modified Copernicus Climate Change Service information". Needs a CDS account.

    CDSAPI_RC=<rc> .venv/bin/python scripts/spread_daily.py [--workers 2] [month ...]   (Copernicus rejects more queued requests)

Writes data/results/spread/daily-mMM.npz per finished calendar month (resumable: finished months are skipped) and
deletes each download once it is folded in.
"""
import concurrent.futures as cf
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spread_yearly import OUT, ROWS, COLS, read, square_index, to_squares  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / 'data/raw/spread-daily'
YEARS = list(range(1981, 2011, 3))
STATS = {'mean': 'daily_mean', 'max': 'daily_maximum', 'min': 'daily_minimum'}
DATASET = 'derived-era5-land-daily-statistics'
# --publish-to DIR: after every folded file write DIR/status.json (progress), and copy each finished month there, so
# progress and results can be fetched over the web (on the server: /srv/climaclue/public/squares/spread-daily-raw).
PUBLISH = None


def status(month, folded):
    if not PUBLISH: return
    PUBLISH.mkdir(parents=True, exist_ok=True)
    done = sorted(int(p.stem[-2:]) for p in OUT.glob('daily-m??.npz'))
    (PUBLISH / 'status.json').write_text(json.dumps({'months_done': done, 'working_on': month, 'files_folded': folded, 'of': 30,
                                                     'updated': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}))


def fetch(year, month, stat):
    import cdsapi
    path = RAW / f't2m-{stat}-{year}-{month:02}.nc'
    if path.exists(): return path
    RAW.mkdir(parents=True, exist_ok=True)
    request = {'variable': '2m_temperature', 'year': str(year), 'month': f'{month:02}', 'day': [f'{d:02}' for d in range(1, 32)],
               'daily_statistic': STATS[stat], 'time_zone': 'utc+00:00', 'frequency': '1_hourly'}
    for attempt in range(30):
        try:
            t = time.time()
            cdsapi.Client(quiet=True).retrieve(DATASET, request, str(path) + '.part')
            Path(str(path) + '.part').rename(path)
            print(f'fetched {path.name} in {time.time() - t:.0f} s', flush=True)
            return path
        except Exception as e:                       # the service limits queued requests per user and sometimes drops one
            print(f'retry {path.name} in {min(10, attempt + 2)} min: {str(e)[:120]}', flush=True); time.sleep(60 * min(10, attempt + 2))
    raise RuntimeError(f'could not fetch {path.name}')


def read_days(path):
    import netCDF4
    with netCDF4.Dataset(path) as ds:
        lat, lon = ds['latitude'][:].data, ds['longitude'][:].data
        v = ds['t2m']
        for i in range(v.shape[0]):
            yield np.ma.filled(v[i].astype(np.float64), np.nan) - 273.15, lat, lon


def do_month(month, workers):
    out = OUT / f'daily-m{month:02}.npz'
    if out.exists():
        print('have', out.name, flush=True); return
    # Checkpoint after every folded file: this machine can be stopped at any time (a cloud container sleeps when its
    # session is idle), and a restart then resumes the month where it stopped instead of starting it again.
    part = OUT / f'daily-m{month:02}.partial.npz'
    keys = ('sd', 'sdd', 'nd', 'sm', 'smm', 'ny')
    acc = {s: {k: np.zeros((ROWS, COLS)) for k in keys} for s in STATS}
    done = set()
    if part.exists():
        z = np.load(part)
        for s_ in STATS:
            for k in keys: acc[s_][k] = z[f'{s_}_{k}'].astype(np.float64)
        done = set(str(x) for x in z['done'])
        print(f'resuming month {month}: {len(done)} files already folded', flush=True)
    jobs = [(y, month, s) for y in YEARS for s in STATS if f'{y}-{s}' not in done]
    idx = None
    with cf.ThreadPoolExecutor(workers) as pool:
        futures = {pool.submit(fetch, *j): j for j in jobs}
        for f in cf.as_completed(futures):
            year, _, stat = futures[f]
            path = f.result()
            A, total, count = acc[stat], np.zeros((ROWS, COLS)), np.zeros((ROWS, COLS))
            for field, lat, lon in read_days(path):
                if idx is None: idx = square_index(lat, lon)
                v = to_squares(field, *idx); ok = np.isfinite(v)
                A['sd'][ok] += v[ok]; A['sdd'][ok] += v[ok] ** 2; A['nd'][ok] += 1
                total[ok] += v[ok]; count[ok] += 1
            monthly = np.where(count >= 25, total / np.maximum(count, 1), np.nan); ok = np.isfinite(monthly)
            A['sm'][ok] += monthly[ok]; A['smm'][ok] += monthly[ok] ** 2; A['ny'][ok] += 1
            path.unlink(); done.add(f'{year}-{stat}')
            OUT.mkdir(parents=True, exist_ok=True)
            np.savez(str(part) + '.tmp.npz', done=np.array(sorted(done)), **{f'{s_}_{k}': acc[s_][k].astype(np.float32 if k in ('sd', 'sm', 'nd', 'ny') else np.float64) for s_ in STATS for k in keys})
            Path(str(part) + '.tmp.npz').replace(part)
            print(f'folded {path.name} ({len(done)}/30)', flush=True)
            status(month, len(done))
    res = {}
    for s, A in acc.items():
        nd, ny = A['nd'], A['ny']
        mean = A['sd'] / np.maximum(nd, 1)
        res[f'day_{s}'] = np.where(nd >= 200, np.sqrt(np.maximum(A['sdd'] / np.maximum(nd, 1) - mean ** 2, 0) * nd / np.maximum(nd - 1, 1)), np.nan).astype(np.float16)
        mm = A['sm'] / np.maximum(ny, 1)
        res[f'year_{s}'] = np.where(ny >= 8, np.sqrt(np.maximum((A['smm'] - ny * mm ** 2) / np.maximum(ny - 1, 1), 0)), np.nan).astype(np.float16)
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, **res, years=np.array(YEARS))
    part.unlink(missing_ok=True)
    if PUBLISH: PUBLISH.mkdir(parents=True, exist_ok=True); shutil.copy(out, PUBLISH / out.name); status(month, 30)
    print('month done', month, flush=True)


if __name__ == '__main__':
    args = sys.argv[1:]
    workers = int(args[args.index('--workers') + 1]) if '--workers' in args else 2
    if '--publish-to' in args: PUBLISH = Path(args[args.index('--publish-to') + 1])
    months = [int(a) for i, a in enumerate(args) if a.isdigit() and (i == 0 or args[i - 1] != '--workers')] or list(range(1, 13))
    for m in months: do_month(m, workers)
