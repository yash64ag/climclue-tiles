# Day-to-day spread download, run on the server

`spread_daily.py` downloads ERA5-Land daily temperature statistics (10 sample years of 1981–2010) month by month from
the Copernicus Climate Data Store and folds them into per-square day-to-day spreads. It takes about a day, mostly
waiting in Copernicus's queue, saves progress after every file and resumes after any restart. Copernicus allows only a
few queued requests per account, so run one copy, with `--workers 2`, and none elsewhere on the same account.

Setup (as root, once):

    mkdir -p /srv/climaclue/spread-work/scripts
    cp /srv/climaclue/public/server/spread/spread_*.py /srv/climaclue/spread-work/scripts/
    python3 -m venv /srv/climaclue/spread-work/venv
    /srv/climaclue/spread-work/venv/bin/pip install -q numpy netCDF4 cdsapi
    # Copernicus key: /root/.cdsapirc, mode 600, two lines:
    #   url: https://cds.climate.copernicus.eu/api
    #   key: <the key from https://cds.climate.copernicus.eu/profile>   (Yash types it in; never paste it into a chat)

Run (survives logouts, restarts on failure, low priority):

    systemd-run --unit=climaclue-spread --property=Restart=on-failure --property=Nice=15 \
      --working-directory=/srv/climaclue/spread-work \
      /srv/climaclue/spread-work/venv/bin/python scripts/spread_daily.py --workers 2 \
      --publish-to /srv/climaclue/public/squares/spread-daily-raw

Progress: `journalctl -u climaclue-spread -n 20` ("folded … (n/30)", "month done N").
Results: `/srv/climaclue/spread-work/data/results/spread/daily-mMM.npz`, one per finished month.

Hand-over is automatic with `--publish-to`: progress at https://climaclue.com/squares/spread-daily-raw/status.json
and each finished month at .../daily-mMM.npz, for the development session to fetch and publish. Delete that folder
once it has. Disk: about 1 GB while running (downloads are deleted as soon as they are folded).
