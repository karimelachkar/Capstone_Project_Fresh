import sys
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logging.info("Starting application")

try:
    # Add the backend directory to the path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
    logging.info("Added backend directory to path")
    
    # Import the create_app function from app.py in the backend directory
    from app import create_app
    logging.info("Imported create_app function")
    
    # Create the application
    app = create_app()
    
    # Add a simple route directly to the app as a fallback
    @app.route('/ping')
    def ping():
        return 'App is running!'
    
    logging.info("Application created successfully")
except Exception as e:
    logging.error(f"Error creating app: {str(e)}")
    # Create a minimal Flask app for error reporting
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/')
    def error():
        return f'Error initializing application: {str(e)}', 500
    
    @app.route('/ping')
    def ping():
        return 'Minimal app is running' 