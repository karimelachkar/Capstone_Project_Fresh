import sys
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logging.info("Starting application")

# Define a variable to store initialization errors
init_error = None

try:
    # Add the backend directory to the path
    backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
    sys.path.insert(0, backend_dir)
    logging.info(f"Added backend directory to path: {backend_dir}")
    
    # Instead of importing 'from app import create_app',
    # Import the module directly to avoid package vs module confusion
    import app as app_module
    logging.info("Imported app module")
    
    # Get the create_app function from the module
    create_app = app_module.create_app
    logging.info("Got create_app function")
    
    # Create the application
    app = create_app()
    
    # Add a simple route directly to the app as a fallback
    @app.route('/api/health')
    def health():
        return {'status': 'ok', 'message': 'App is running'}
    
    logging.info("Application created successfully")
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