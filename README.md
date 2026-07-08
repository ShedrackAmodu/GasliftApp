# Gas Lift Opportunity Automation System

A Django web app for identifying gas lift candidate wells using well test data.

## What it does

- User login and profile management
- Upload CSV or Excel well test data
- Map columns to required fields
- Preview uploaded data
- Run trend analysis and score candidate wells
- Export results to Excel or CSV

## Quick Start

1. Create a virtual environment:
```bash
python -m venv venv
venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run migrations:
```bash
python manage.py migrate
```

4. Create an admin user:
```bash
python manage.py createsuperuser
```

5. Start the server:
```bash
python manage.py runserver
```

6. Open `http://localhost:8000`

## Upload Workflow

1. Login or sign up
2. Upload a CSV or Excel file
3. Map columns to the required fields
4. Preview the data
5. Run analysis and review ranked results
6. Export results if needed

## Required Fields

- Well
- Date
- BS&W (%)
- Net Oil (bopd)
- Form.GLR (scf/bbl)
- Prod Method
- Test Status
- Tubing Pressure (psi)
- Flow Line Pressure (psi)
- Well Choke Size

Field names can be mapped during upload.

## Project Layout

- `gaslift_config/` — Django settings and app URLs
- `apps/accounts/` — authentication and profiles
- `apps/data_upload/` — upload, mapping, preview
- `apps/analysis/` — trend analysis and scoring
- `apps/results/` — results display and export
- `templates/` — HTML templates
- `static/` — CSS, JavaScript, images
- `media/` — uploaded files

## Notes

- Uses SQLite by default
- Best for local development
- Configure a real database and secrets for deployment
