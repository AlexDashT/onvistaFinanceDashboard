# onvistaFinanceDashboard

Local-first financial dashboard built with Python and Streamlit for monitoring a watchlist of onvista instruments.

## Current status

This repository currently includes:

- watchlist management in the Streamlit sidebar
- adding instruments by ISIN, WKN, free-text name, or direct onvista URL
- local JSON persistence under `data/`
- disk caching for onvista resolution and chart data
- local in-app price charts rendered with Plotly
- a dedicated Streamlit settings page for layout and cache settings
- basic automated tests with `pytest`

The current app is intentionally small and local-first. It is structured so it can later be deployed as a hosted Streamlit app with minimal architecture changes.

## Tech stack

- Python 3.12+
- Streamlit
- pandas
- httpx
- beautifulsoup4
- pydantic
- plotly
- kaleido
- playwright
- tenacity
- rapidfuzz
- pytest

## Project structure

```text
finance_dashboard/
  app.py
  requirements.txt
  README.md
  .gitignore
  data/
    watchlist.json
    settings.json
    cache/
    exports/
  pages/
    Settings.py
  src/
    config.py
    models.py
    storage.py
    providers/
      base.py
      onvista_resolver.py
      onvista_history_provider.py
    services/
      cache_service.py
      chart_service.py
      instrument_service.py
    ui/
      cards.py
      charts.py
      sidebar.py
      theme.py
    utils/
      logging_utils.py
      text_utils.py
  tests/
    test_chart_service.py
    test_models.py
    test_storage.py
```

## Features

### Dashboard

- local chart rendering inside the app
- period selector for `1D`, `1W`, `1M`, `3M`, `1Y`, `3Y`, `5Y`, and `MAX`
- per-instrument error handling so one bad instrument does not crash the whole page

### Watchlist

- add by ISIN
- add by WKN
- add by free-text name with selectable matches
- add by direct onvista URL
- remove instruments
- reorder instruments

### Settings

- change dashboard grid columns
- change cache TTL
- change search result limit
- toggle HTML snapshot export preference

### Persistence

- `data/watchlist.json`
- `data/settings.json`
- cached provider responses in `data/cache/`

## Local setup

### 1. Create and activate a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Install Playwright Chromium

```powershell
python -m playwright install chromium
```

### 4. Run the dashboard

```powershell
python -m streamlit run app.py
```

The app will start locally, typically at:

```text
http://localhost:8501
```

## One-file VPS install for Ubuntu

This repository includes a single interactive deployment script:

```bash
./deploy.sh
```

The script is designed for Ubuntu VPS deployment and will ask for the values it needs during setup, including:

- domain or subdomain
- install directory
- Linux app user
- git repository URL
- branch
- reverse proxy choice
- whether Playwright Chromium should be installed
- whether `ufw` should be configured

### Default recommendation

The script defaults to `Caddy`, which is the recommended choice for this project because it is simpler than Nginx and handles HTTPS automatically in the common single-domain VPS case.

The deployment script installs Caddy from the official Caddy APT repository on Ubuntu, so you do not need to preinstall it yourself.

### Quick start on a fresh Ubuntu VPS

```bash
git clone https://github.com/AlexDashT/onvistaFinanceDashboard.git
cd onvistaFinanceDashboard
chmod +x deploy.sh
sudo ./deploy.sh
```

### What the script does

- installs required Ubuntu packages
- clones or updates the repository
- creates a Python virtual environment
- installs Python dependencies
- optionally installs Playwright Chromium
- creates a `systemd` service for Streamlit
- configures `Caddy` or `Nginx`
- optionally configures `ufw`

### Important before you run it

- point your domain or subdomain to the VPS first
- make sure you can use `sudo`
- for Nginx + Certbot, have an email ready for Let's Encrypt
- Caddy is the easiest default unless you specifically want Nginx

## Streamlit pages

- Main dashboard: `app.py`
- Settings page: `pages/Settings.py`

## Data files

### `data/watchlist.json`

Example:

```json
[
  {
    "display_name": "Oberbank Premium Strategie defensiv - I EUR ACC",
    "isin": "AT0000A20UD5",
    "wkn": "A2JH4L",
    "onvista_url": "https://www.onvista.de/fonds/OBERBANK-PREMIUM-STRATEGIE-DEFENSIV-I-EUR-ACC-Fonds-AT0000A20UD5",
    "instrument_type": "fund",
    "currency": "EUR",
    "source_label": "KVG"
  }
]
```

### `data/settings.json`

Stores app-level UI settings such as:

- selected chart period
- dashboard column count
- cache TTL
- export preference
- search result limit

## Running tests

```powershell
python -m pytest -q
```

## Packaging notes for Windows

This project is built for correctness and maintainability first, not packaging first.

For local use, the recommended run command is still:

```powershell
python -m streamlit run app.py
```

If you want to package it later with PyInstaller, you will usually want a dedicated launcher script that starts Streamlit programmatically. That packaging wrapper is not included yet, so treat PyInstaller support as a documented next step rather than a finished feature in the current repository state.

## Deployment notes for web

The app is already structured for later deployment as a web dashboard:

- no database dependency
- JSON-based local persistence
- provider logic isolated from UI code
- Streamlit-native interface

For hosted deployment, the main adjustments will likely be:

- replacing local JSON files with a deployment-safe storage option
- setting writable cache/export directories for the hosting platform
- installing Playwright browser dependencies on the target host if browser-based features are added later

## Limitations

- this project depends on onvista page and API structures that can change over time
- screenshot-based chart fallback is not implemented yet
- chart image export is not implemented yet
- HTML snapshot export is only a stored preference at the moment
- this repository currently focuses on local charts, watchlist management, and app structure

## Troubleshooting

### `streamlit` is not recognized

Use:

```powershell
python -m streamlit run app.py
```

### Playwright browser is missing

Run:

```powershell
python -m playwright install chromium
```

### onvista search or chart fails

Possible causes:

- network timeout
- temporary onvista outage
- changed page structure
- changed onvista API shape

Try:

- refreshing the app
- searching the instrument again
- clearing cached files from `data/cache/`

### Settings file fails to load

Delete the local `data/settings.json` and restart the app to regenerate defaults.

## Notes

This repository contains a sample `watchlist.json` and default `settings.json` so the app can be started immediately after cloning.
