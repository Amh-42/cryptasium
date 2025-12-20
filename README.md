# Cryptasium Flask Application

A modern Flask web application for managing and displaying tech content including blogs, YouTube videos, podcasts, shorts, and community posts.

## Features

- **Content Management**: Admin panel for managing all content types
- **SQLite Database**: Simple, optimized database schema
- **Modern UI**: Beautiful, responsive design with interactive elements
- **cPanel Ready**: Configured for easy deployment on cPanel hosting

## Project Structure

```
cryptasium/
├── app.py                 # Main Flask application
├── models.py              # Database models
├── config.py              # Configuration settings
├── wsgi.py                # WSGI entry point for cPanel
├── requirements.txt       # Python dependencies
├── .htaccess             # Apache configuration for cPanel
├── templates/            # Jinja2 templates
│   ├── base.html         # Base template
│   ├── index.html        # Homepage
│   ├── blog.html         # Blog listing
│   ├── youtube.html      # YouTube videos
│   ├── podcast.html      # Podcast episodes
│   ├── shorts.html       # Short videos
│   ├── community.html    # Community posts
│   └── admin/           # Admin templates
├── static/              # Static files
│   ├── css/            # Stylesheets
│   └── js/             # JavaScript files
└── instance/           # Database files (created automatically)
```

## Installation

### Local Development

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd cryptasium
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set environment variables** (optional)
   ```bash
   export FLASK_ENV=development
   export SECRET_KEY=your-secret-key-here
   export ADMIN_USERNAME=admin
   export ADMIN_PASSWORD=your-secure-password
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

6. **Access the application**
   - Website: http://localhost:5000
   - Admin Panel: http://localhost:5000/admin
   - Default credentials: admin / admin123 (change in production!)

### cPanel Deployment

1. **Upload files to cPanel**
   - Upload all files to your `public_html` directory (or subdirectory)

2. **Set up Python App in cPanel**
   - Go to cPanel → Software → Setup Python App
   - Create a new application
   - Set Python version (3.8+ recommended)
   - Set application root to your project directory
   - Set application URL (e.g., `/` or `/cryptasium`)
   - Set startup file to `wsgi.py`
   - Click "Create"

3. **Install dependencies**
   - In cPanel Python App, click "Install requirements"
   - Or SSH and run: `pip install -r requirements.txt`

4. **Configure environment variables**
   - In cPanel Python App settings, add environment variables:
     - `FLASK_ENV=production`
     - `SECRET_KEY=your-secret-key-here`
     - `ADMIN_USERNAME=your-admin-username`
     - `ADMIN_PASSWORD=your-secure-password`

5. **Set file permissions**
   ```bash
   chmod 755 app.py wsgi.py
   chmod 777 instance/  # For database directory
   ```

6. **Restart the application**
   - In cPanel Python App, click "Restart"

## Database

The application uses SQLite by default. The database file is created automatically in the `instance/` directory.

### Database Models

- **BlogPost**: Blog articles with title, content, excerpt, featured image
- **YouTubeVideo**: YouTube videos with video ID, thumbnail, description
- **Podcast**: Podcast episodes with audio URL, thumbnail, description
- **Short**: Short videos with video ID, thumbnail, description
- **CommunityPost**: Community posts with title, content, category

### Initializing Database

The database is created automatically on first run. To reset:

```python
from app import create_app
from models import db

app = create_app()
with app.app_context():
    db.drop_all()
    db.create_all()
```

## Admin Panel

Access the admin panel at `/admin` after logging in.

### Default Credentials
- Username: `admin`
- Password: `admin123`

**⚠️ IMPORTANT: Change these credentials in production!**

Set environment variables:
- `ADMIN_USERNAME=your-username`
- `ADMIN_PASSWORD=your-secure-password`

## Configuration

Edit `config.py` to customize:

- Database URI
- Pagination settings
- Admin credentials
- Secret key

## Security Notes

1. **Change default admin credentials** before deploying
2. **Set a strong SECRET_KEY** for production
3. **Use environment variables** for sensitive data
4. **Enable HTTPS** on your cPanel hosting
5. **Regular backups** of the database file

## Development

### Running in Development Mode

```bash
export FLASK_ENV=development
python app.py
```

### Adding New Content Types

1. Create model in `models.py`
2. Add routes in `app.py`
3. Create templates in `templates/`
4. Add admin routes for content management

## License

© 2025 Cryptasium Media. All rights reserved.

## Support

For issues or questions, contact: hello@cryptasium.com
