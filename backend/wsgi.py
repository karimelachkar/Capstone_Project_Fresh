"""
WSGI module for App Engine deployment.
"""
import os
import sys

# Add the current directory to Python's path
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import create_app from app.py in the same directory
from backend.app import create_app

# Create the application
app = create_app()
