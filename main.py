import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Import the create_app function from app.py in the backend directory
from app import create_app

# Create the application
app = create_app() 