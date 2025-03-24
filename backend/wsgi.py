"""
WSGI module for App Engine deployment.
"""
import os
import sys

# Add the current directory to Python's path
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import create_app directly from the backend/app.py file
import importlib.util
app_path = os.path.join(os.path.dirname(__file__), "app.py")
spec = importlib.util.spec_from_file_location("app_module", app_path)
app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_module)

# Create the application
app = app_module.create_app()
