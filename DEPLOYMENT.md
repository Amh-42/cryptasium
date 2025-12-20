# Deployment Guide for cPanel

## Quick Deployment Steps

### 1. Upload Files
Upload all project files to your cPanel hosting directory (usually `public_html` or a subdirectory).

### 2. Set Up Python App in cPanel
1. Log into cPanel
2. Navigate to **Software** → **Setup Python App**
3. Click **Create Application**
4. Configure:
   - **Python version**: 3.8 or higher
   - **Application root**: Your project directory (e.g., `/home/username/public_html/cryptasium`)
   - **Application URL**: `/` or `/cryptasium` (depending on your setup)
   - **Application startup file**: `wsgi.py`
   - **Application Entry point**: `application`
5. Click **Create**

### 3. Install Dependencies
In the Python App interface, click **Install requirements** or use SSH:
```bash
cd /home/username/public_html/cryptasium
pip install -r requirements.txt
```

### 4. Set Environment Variables
In cPanel Python App settings, add:
- `FLASK_ENV=production`
- `SECRET_KEY=your-strong-secret-key-here`
- `ADMIN_USERNAME=your-admin-username`
- `ADMIN_PASSWORD=your-secure-password`

### 5. Set File Permissions
```bash
chmod 755 app.py wsgi.py
chmod 777 instance/
```

### 6. Restart Application
Click **Restart** in the Python App interface.

## Database Initialization

The database will be created automatically on first run. To manually initialize:

```python
from app import create_app
from models import db

app = create_app('production')
with app.app_context():
    db.create_all()
```

## Troubleshooting

### Common Issues

1. **500 Internal Server Error**
   - Check file permissions
   - Verify Python version (3.8+)
   - Check error logs in cPanel

2. **Database Errors**
   - Ensure `instance/` directory is writable (chmod 777)
   - Check database path in `config.py`

3. **Import Errors**
   - Verify all dependencies are installed
   - Check Python path in cPanel

4. **Static Files Not Loading**
   - Ensure `static/` directory exists
   - Check file permissions

## Security Checklist

- [ ] Change default admin credentials
- [ ] Set strong SECRET_KEY
- [ ] Enable HTTPS/SSL
- [ ] Set proper file permissions
- [ ] Regular database backups
- [ ] Keep dependencies updated

## Backup Strategy

1. **Database**: Backup `instance/cryptasium.db` regularly
2. **Files**: Backup entire project directory
3. **Automated**: Set up cPanel backup schedule

## Post-Deployment

1. Test all routes
2. Verify admin panel access
3. Create initial content
4. Test pagination
5. Verify static assets load correctly

