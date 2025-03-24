import sys
import os
import logging
import importlib.util

# Configure logging
logging.basicConfig(level=logging.INFO)
logging.info("Starting application")

# Define a variable to store initialization errors
init_error = None

try:
    # Get absolute path to app.py
    backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
    app_path = os.path.join(backend_dir, 'app.py')
    logging.info(f"Looking for app.py at: {app_path}")
    
    # Check if the file exists
    if not os.path.exists(app_path):
        raise FileNotFoundError(f"app.py not found at {app_path}")
    
    # List all files in backend for debugging
    logging.info(f"Files in backend directory: {os.listdir(backend_dir)}")
    
    # Load app.py directly, bypassing normal import system
    spec = importlib.util.spec_from_file_location("app_module", app_path)
    app_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app_module)
    logging.info(f"Successfully loaded app_module from {app_path}")
    
    # List all attributes of the module for debugging
    logging.info(f"Attributes in app_module: {dir(app_module)}")
    
    # Check if create_app function exists
    if not hasattr(app_module, 'create_app'):
        logging.error(f"Module does not have create_app function. Available attributes: {dir(app_module)}")
        raise AttributeError("Module does not have create_app function")
    
    # Get the create_app function
    create_app = app_module.create_app
    logging.info("Got create_app function")
    
    # Create the application
    app = create_app()
    logging.info("Application created successfully")
    
    # Add a simple route directly to the app as a fallback
    @app.route('/api/health')
    def health():
        return {'status': 'ok', 'message': 'App is running'}
    
except Exception as e:
    logging.error(f"Error creating app: {str(e)}")
    # Store the error message for the error handler
    init_error = str(e)
    # Create a minimal Flask app for error reporting
    from flask import Flask, jsonify
    app = Flask(__name__)
    
    @app.route('/')
    def error():
        return f'Error initializing application: {init_error}', 500
    
    @app.route('/api/health')
    def health():
        return jsonify({'status': 'error', 'message': init_error})

# Only used when running locally
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True) 