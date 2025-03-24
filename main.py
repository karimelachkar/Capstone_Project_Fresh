# This file is required by App Engine as the entrypoint
# Import the app from the WSGI module
from backend.wsgi import app

# No need to run the app here - gunicorn does that 