# Gas Lift Opportunity Automation System - Django

A smart web-based tool for identifying wells that are good candidates for gas lift installation based on well test data analysis.

## Features

- **User Authentication**: Secure login and profile management
- **File Upload**: Upload well test data in Excel (.xlsx) or CSV (.csv) format
- **Column Mapping**: Flexible mapping of your data columns to required fields
- **Data Preview**: Review your data before analysis
- **Parameter Weighting**: Adjust the importance of each analysis parameter
- **Trend Analysis**: View individual well performance trends with charts
- **Automated Analysis**: Statistical analysis using Mann-Kendall test and Sen's slope
- **Results Ranking**: Wells ranked by gas lift candidate score
- **Export**: Download results in Excel or CSV format
- **Responsive Design**: Works on desktop, tablet, and mobile devices

## Installation

### Prerequisites
- Python 3.8+
- pip (Python package manager)
- Git

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd gaslift_project
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Apply migrations:
```bash
python manage.py migrate
```

5. Create an admin user:
```bash
python manage.py createsuperuser
```

6. Run development server:
```bash
python manage.py runserver
```

7. Access the application:
- Main app: http://localhost:8000
- Admin panel: http://localhost:8000/admin

## Usage

### Step-by-Step Workflow

1. **Sign Up / Login**: Create an account or log in
2. **Upload Data**: Upload your well test data (Excel or CSV)
3. **Map Columns**: Match your data columns to required fields
4. **Preview Data**: Review the first 50 rows of your data
5. **Adjust Weights**: Set parameter importance (optional)
6. **View Trends**: Explore individual well trends with charts
7. **Run Analysis**: Execute the trend analysis and ranking
8. **Review Results**: See ranked candidate wells
9. **Export**: Download results for reporting

## Data Requirements

Your file must contain these columns:
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

Column names don't need to match exactly - you'll map them during upload.

## Project Structure

```
gaslift_project/
├── gaslift_config/        # Django settings & core URLs
├── apps/
│   ├── accounts/          # User authentication & profiles
│   ├── data_upload/       # File upload & column mapping
│   ├── analysis/          # Trend analysis & ranking logic
│   └── results/           # Results display & export
├── templates/             # HTML templates
├── static/                # CSS, JavaScript, images
├── media/                 # Uploaded files
├── manage.py              # Django management script
└── requirements.txt       # Python dependencies
```

## Analysis Logic

The system uses statistical methods to identify gas lift candidates:

1. **Mann-Kendall Test**: Determines if trends are real or random
2. **Sen's Slope**: Calculates the rate of change for each trend
3. **Magnitude Classification**: Classifies trends as Slightly, Moderately, or Aggressively changing
4. **Candidate Scoring**: Combines all factors with user-defined weights

## API Endpoints

- `POST /api/auth/signup/` - User registration
- `POST /api/auth/login/` - User login
- `GET /api/auth/logout/` - User logout
- `GET /api/auth/profile/` - User profile
- `POST /api/upload/upload/` - Upload file
- `GET/POST /api/upload/<id>/mapping/` - Column mapping
- `GET /api/upload/<id>/preview/` - Preview data
- `GET/POST /api/analysis/<id>/weights/` - Adjust weights
- `GET /api/analysis/<id>/trends/` - View trends
- `POST /api/analysis/<id>/run/` - Run analysis
- `GET /api/results/<id>/view/` - View results
- `GET /api/results/<id>/export-excel/` - Export to Excel
- `GET /api/results/<id>/export-csv/` - Export to CSV

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```
DEBUG=True
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///db.sqlite3
ALLOWED_HOSTS=localhost,127.0.0.1
```

### Database

Default: SQLite (development)

For production, use PostgreSQL:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'gaslift',
        'USER': 'postgres',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

## Troubleshooting

### File Upload Issues
- Ensure file is in .xlsx or .csv format
- Maximum file size: 100 MB
- Columns must match required fields

### Analysis Not Running
- Ensure at least 5 data points per well
- Check that numeric columns contain valid numbers
- Verify date column is in valid date format

### Permission Issues
- Run migrations: `python manage.py migrate`
- Create superuser: `python manage.py createsuperuser`

## Development

### Running Tests
```bash
python manage.py test
```

### Creating New Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### Collecting Static Files
```bash
python manage.py collectstatic --noinput
```

## Deployment

### Using Gunicorn
```bash
pip install gunicorn
gunicorn gaslift_config.wsgi:application --bind 0.0.0.0:8000
```

### Using Docker
```dockerfile
FROM python:3.10
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "gaslift_config.wsgi:application", "--bind", "0.0.0.0:8000"]
```

## Documentation

See [USER_MANUAL.md](USER_MANUAL.md) for detailed user documentation.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

© 2026 Gas Lift Automation Project. All rights reserved.

## Support

For technical support, contact your system administrator or visit the help section in the application.

## Changelog

### Version 1.0.0 (2026-01-01)
- Initial release
- Core functionality for well analysis and ranking
- User authentication and file upload
- Trend analysis with Mann-Kendall test
- Results export in Excel and CSV formats
