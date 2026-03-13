# Fundraising SaaS MVP

A minimal browser-based MVP for the backend/product logic of a fundraising SaaS.

## What you can open in the browser

- Login page: `/login`
- Dashboard page: `/dashboard`
- Materials tool page: `/materials`
- Investor pipeline page: `/pipeline`

These pages are enough to log in and navigate a small 3-page MVP flow.

## Installation (local computer)

You only need Python 3.10+ installed.

- macOS (Homebrew): `brew install python`
- Ubuntu/Debian: `sudo apt-get install python3`
- Windows: install Python from https://www.python.org/downloads/

No Python packages are required.

## Run locally

```bash
python server.py
```

Then open in your browser:

- `http://127.0.0.1:8000/login`

Default bind is preview-friendly: `0.0.0.0:8000`.

## API still available

- `GET /health`
- `POST /founders/{founder_id}/plan?plan=pro`
- `POST /startups`
- `POST /investors`
- `GET /investors`
- `PATCH /investors/{investor_id}/pipeline`
- `POST /match/{founder_id}/{startup_id}`
- `POST /materials/email`
- `POST /materials/update`
- `POST /materials/deck`

## Run tests

```bash
python -m unittest -v
```

## Files

- `app.py` → in-memory SaaS domain logic
- `server.py` → browser pages + HTTP API + login/session flow
- `test_app.py` → domain tests
- `test_server.py` → HTTP + login/page flow tests
