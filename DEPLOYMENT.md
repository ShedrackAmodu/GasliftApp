# Deployment Guide for PythonAnywhere

This guide walks you through deploying the Gaslift App on PythonAnywhere.

## Prerequisites

- A PythonAnywhere account (free tier works, but paid tier recommended for production)
- Your GitHub repository: https://github.com/ShedrackAmodu/GasliftApp

## Step 1: Clone the Repository on PythonAnywhere

1. Log in to your PythonAnywhere account at https://www.pythonanywhere.com/
2. Open a **Bash console** from the Dashboard
3. Clone your repository:
   ```bash
   git clone https://github.com/ShedrackAmodu/GasliftApp.git
   cd GasliftApp
   ```

## Step 2: Create a Virtual Environment

```bash
mkvirtualenv --python=/usr/bin/python3.10 gaslift-env
pip install --upgrade pip
pip install -r requirements.txt
```

## Step 3: Create Environment Variables

```bash
cd ~/GasliftApp
nano .env
```

Add the following content (replace with your own secret key):
```
SECRET_KEY=your-generated-secret-key-here
DEBUG=False
ALLOWED_HOSTS=Amodu.pythonanywhere.com
```

Generate a secret key at: https://djecrety.ir/

## Step 4: Run Migrations and Collect Static Files

```bash
cd ~/GasliftApp
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

## Step 5: Configure the Web App on PythonAnywhere

1. Go to the **Web** tab in PythonAnywhere
2. Click **Add a new web app**
3. Choose **Manual configuration** (not the Django wizard)
4. Select **Python 3.10** and click Next

### Virtual Environment
- In the **Virtualenv** section, enter: `/home/Amodu/.virtualenvs/gaslift-env`

### Code
- **Source code**: `/home/Amodu/GasliftApp`
- **Working directory**: `/home/Amodu/GasliftApp`

### WSGI Configuration File
Click on the WSGI configuration file link and replace its contents with:

```python
import os
import sys

# Add your project directory to the sys.path
path = '/home/Amodu/GasliftApp'
if path not in sys.path:
    sys.path.append(path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'gaslift_config.settings'

# Load the .env file
from dotenv import load_dotenv
dotenv_path = os.path.join(path, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

### Static Files
In the **Static files** section, add:

| URL | Directory |
|-----|-----------|
| `/static/` | `/home/Amodu/GasliftApp/staticfiles` |
| `/media/` | `/home/Amodu/GasliftApp/media` |

## Step 6: Reload and Test

1. Click the **Reload** button for your web app
2. Visit https://Amodu.pythonanywhere.com/ to see your app

## Troubleshooting

### Error logs
Check the **Error log** and **Server log** in the Web tab for any issues.

### Permission issues
If you get permission errors with media uploads:
```bash
chmod 755 ~/GasliftApp/media
```

### Database issues
If you need to reset the database:
```bash
cd ~/GasliftApp
rm db.sqlite3
python manage.py migrate
python manage.py createsuperuser
```

### Static files not loading
```bash
cd ~/GasliftApp
python manage.py collectstatic --noinput
```

## Updating the App

When you make changes to your GitHub repo:

```bash
cd ~/GasliftApp
git pull origin main
workon gaslift-env
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
# Then reload your web app from the PythonAnywhere Web tab