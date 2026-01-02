"""
WSGI entry point for cPanel deployment
"""
import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, socketio

# Create the Flask application
app = create_app('production')
application = socketio.WSGIApp(socketio, app)

if __name__ == "__main__":
    application.run()

