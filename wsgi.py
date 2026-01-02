"""
WSGI entry point for cPanel deployment
"""
import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app

# Create the Flask application
application = create_app('production')

if __name__ == "__main__":
    application.run()

