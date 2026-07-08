# DEVELOPMENT GUIDE - Gas Lift System

## Project Architecture

### Directory Structure
```
gaslift_project/
├── gaslift_config/           # Django configuration & settings
│   ├── settings.py           # Main Django settings
│   ├── urls.py               # URL routing configuration
│   ├── wsgi.py               # WSGI application
│   └── asgi.py               # ASGI application
│
├── apps/
│   ├── accounts/             # User authentication & profiles
│   │   ├── models.py         # User and profile models
│   │   ├── views.py          # Auth views (login, signup, profile)
│   │   ├── urls.py           # Auth URLs
│   │   └── admin.py          # Django admin configuration
│   │
│   ├── data_upload/          # File upload & column mapping
│   │   ├── models.py         # DataUpload, ColumnMapping, PreviewData
│   │   ├── views.py          # Upload, mapping, preview views
│   │   ├── utils.py          # Data processor utilities
│   │   └── forms.py          # Upload and mapping forms
│   │
│   ├── analysis/             # Trend analysis & ranking
│   │   ├── models.py         # AnalysisSession, AnalysisWeights, WellTrendAnalysis
│   │   ├── views.py          # Analysis workflow views
│   │   ├── utils.py          # TrendAnalyzer, statistical calculations
│   │   └── forms.py          # Weight adjustment forms
│   │
│   └── results/              # Results display & export
│       ├── views.py          # Results, export views
│       └── urls.py           # Results URLs
│
├── templates/                # HTML templates
│   ├── base/                 # Base templates
│   ├── accounts/             # Auth templates
│   ├── data_upload/          # Upload templates
│   ├── analysis/             # Analysis templates
│   └── results/              # Results templates
│
├── static/                   # CSS, JS, images
├── media/                    # Uploaded files
├── logs/                     # Application logs
├── manage.py                 # Django management
├── requirements.txt          # Python dependencies
├── README.md                 # Project overview
├── USER_MANUAL.md           # User documentation
├── INSTALLATION.md          # Installation guide
└── DEVELOPMENT.md           # This file
```

## Models Overview

### Accounts App
- **UserProfile**: Extended user information (company, department, role)

### Data Upload App
- **DataUpload**: Stores uploaded files metadata
- **ColumnMapping**: Maps user columns to required fields
- **PreviewData**: Stores sample data and quality report

### Analysis App
- **AnalysisSession**: Represents an analysis run
- **AnalysisWeights**: Parameter weights for analysis
- **WellTrendAnalysis**: Individual well trend results

### Results App
- No custom models (uses analysis models for display)

## Development Workflow

### Adding a New Feature

1. **Design the Model** (if needed)
   - Edit `apps/your_app/models.py`
   - Run `python manage.py makemigrations`
   - Run `python manage.py migrate`

2. **Create Views**
   - Edit `apps/your_app/views.py`
   - Create corresponding templates
   - Register URLs in `apps/your_app/urls.py`

3. **Create Templates**
   - Add HTML templates in `templates/your_app/`
   - Use Bootstrap 5 for styling
   - Inherit from `base/base.html`

4. **Update URLs**
   - Register routes in app's `urls.py`
   - Include in main `gaslift_config/urls.py`

5. **Test Thoroughly**
   - Test all user flows
   - Check error handling
   - Verify data validation

### Common Tasks

#### Create a Django Admin Page
```python
# In your_app/admin.py
from django.contrib import admin
from .models import YourModel

@admin.register(YourModel)
class YourModelAdmin(admin.ModelAdmin):
    list_display = ('field1', 'field2', 'field3')
    search_fields = ('field1', 'field2')
    list_filter = ('created_at',)
```

#### Create a View
```python
# In your_app/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

@login_required(login_url='accounts:login')
def your_view(request):
    if request.method == 'POST':
        # Handle POST
        return redirect('some_view')
    
    context = {'data': 'value'}
    return render(request, 'your_app/template.html', context)
```

#### Create a Template
```html
{% extends "base/base.html" %}

{% block title %}Page Title{% endblock %}

{% block content %}
<div class="col-12">
    <div class="card">
        <div class="card-header">
            <h3>Header</h3>
        </div>
        <div class="card-body">
            <!-- Your content -->
        </div>
    </div>
</div>
{% endblock %}
```

## Testing

### Run Tests
```bash
python manage.py test
```

### Test a Specific App
```bash
python manage.py test apps.accounts
```

### Test with Coverage
```bash
pip install coverage
coverage run --source='.' manage.py test
coverage report
```

## Debugging

### Enable Debug Toolbar
```bash
pip install django-debug-toolbar
```

Add to INSTALLED_APPS in settings.py:
```python
INSTALLED_APPS = [
    ...
    'debug_toolbar',
]
```

### Check Database
```bash
python manage.py dbshell
```

### View Logs
```bash
tail -f logs/gaslift.log
```

## Performance Optimization

### Database Queries
- Use `select_related()` for ForeignKey
- Use `prefetch_related()` for ManyToMany
- Use `only()` and `defer()` to limit fields

### Caching
```python
from django.core.cache import cache

cache.set('key', value, 3600)  # 1 hour
value = cache.get('key')
```

### Async Tasks
For long-running operations, use Celery:
```bash
pip install celery redis
```

## Deployment

### Environment Variables
Create `.env` and set:
```
DEBUG=False
SECRET_KEY=your-secret-key
ALLOWED_HOSTS=yourdomain.com
DATABASE_URL=postgresql://user:pass@host/db
```

### Collectstatic
```bash
python manage.py collectstatic --noinput
```

### Run with Gunicorn
```bash
gunicorn gaslift_config.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

### Docker
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "gaslift_config.wsgi:application", "--bind", "0.0.0.0:8000"]
```

## Security Considerations

1. **Never commit secrets** to version control
2. **Use HTTPS** in production
3. **Validate all inputs** on both frontend and backend
4. **Use CSRF protection** (enabled by default)
5. **Keep dependencies updated**: `pip install --upgrade pip`
6. **Run security checks**: `python manage.py check --deploy`

## Code Style Guidelines

- Follow PEP 8
- Use meaningful variable names
- Add docstrings to functions
- Keep functions small and focused
- Use type hints where possible

## Contributing

1. Create a feature branch
2. Make your changes
3. Write tests
4. Update documentation
5. Submit a pull request

## Useful Commands

```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Create demo user
python create_demo_user.py

# Run shell
python manage.py shell

# View URLs
python manage.py show_urls

# Collect static files
python manage.py collectstatic --noinput

# Reset database
python manage.py flush

# Run tests
python manage.py test

# Check system status
python manage.py check
```

## Troubleshooting Development Issues

### ModuleNotFoundError
- Make sure virtual environment is activated
- Reinstall requirements: `pip install -r requirements.txt`

### Port Already in Use
- Use different port: `python manage.py runserver 8001`
- Kill process on port 8000: `lsof -ti:8000 | xargs kill -9` (macOS/Linux)

### Static Files Not Loading
- Run: `python manage.py collectstatic --noinput`
- Check STATIC_ROOT and STATIC_URL in settings

### Template Not Found
- Check template path matches app structure
- Ensure app is in INSTALLED_APPS
- Verify TEMPLATES configuration in settings

For more help, see README.md or USER_MANUAL.md
