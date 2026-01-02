"""
Configuration file for Cryptasium Flask application
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).parent.resolve()

# Ensure instance directory exists
INSTANCE_DIR = BASE_DIR / 'instance'
INSTANCE_DIR.mkdir(exist_ok=True)

# Database path (absolute)
DB_PATH = INSTANCE_DIR / 'cryptasium.db'

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Use environment variable if set, otherwise use absolute path
    # Note: For SQLite, use sqlite:/// followed by absolute path
    _db_url = os.environ.get('DATABASE_URL')
    if _db_url and _db_url.startswith('sqlite:///instance/'):
        # Convert relative path to absolute
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{DB_PATH}'
    elif _db_url:
        SQLALCHEMY_DATABASE_URI = _db_url
    else:
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{DB_PATH}'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Admin credentials (change in production)
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') or 'admin'
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'admin123'
    
    # Pagination
    POSTS_PER_PAGE = int(os.environ.get('POSTS_PER_PAGE', 12))
    VIDEOS_PER_PAGE = int(os.environ.get('VIDEOS_PER_PAGE', 12))
    SHORTS_PER_PAGE = int(os.environ.get('SHORTS_PER_PAGE', 20))
    
    # Media
    UPLOAD_FOLDER = BASE_DIR / 'static' / 'uploads'

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

