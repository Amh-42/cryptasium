# Flask Application Setup Guide

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the application:**
   ```bash
   python app.py
   ```

3. **Access:**
   - Website: http://localhost:5000
   - Admin: http://localhost:5000/admin (admin/admin123)

## Next Steps

The Flask application structure has been created with:
- ✅ Database models (BlogPost, YouTubeVideo, Podcast, Short, CommunityPost)
- ✅ Main application file (app.py) with routes
- ✅ Configuration file (config.py)
- ✅ WSGI entry point (wsgi.py) for cPanel
- ✅ Requirements file (requirements.txt)
- ✅ .htaccess for cPanel deployment
- ✅ README with full documentation

## Templates Needed

You need to create the following templates by extracting from your HTML files:

1. **templates/base.html** - Base template with all CSS/JS (extract from index.html)
2. **templates/index.html** - Homepage template
3. **templates/blog.html** - Blog listing
4. **templates/blog_detail.html** - Blog post detail
5. **templates/youtube.html** - YouTube videos listing
6. **templates/podcast.html** - Podcast episodes listing
7. **templates/shorts.html** - Shorts listing
8. **templates/community.html** - Community posts listing
9. **templates/admin/** - Admin panel templates

## Template Conversion Process

1. Extract common elements (navbar, footer, CSS, JS) to `base.html`
2. Convert static HTML files to Jinja2 templates
3. Replace hardcoded content with dynamic data from database
4. Use Flask's `url_for()` for all links

## Database Initialization

The database will be created automatically on first run in the `instance/` directory.

To manually initialize:
```python
from app import create_app
from models import db

app = create_app()
with app.app_context():
    db.create_all()
```

## cPanel Deployment

1. Upload all files to your cPanel hosting
2. Set up Python App in cPanel
3. Point to `wsgi.py` as the startup file
4. Install requirements via cPanel or SSH
5. Set environment variables in cPanel Python App settings

See README.md for detailed deployment instructions.

