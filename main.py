# This file is required by App Engine as the entrypoint
# Import the app directly from backend/app.py
from backend.app import app

# No need to run the app here - gunicorn does that 