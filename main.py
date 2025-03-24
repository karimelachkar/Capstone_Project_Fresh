import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

# Add the current directory to Python's path if it's not already there
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
    logging.info(f"Added {current_dir} to Python path")

# Now import the app creation function
from backend.app import create_app

# Create the application
app = create_app()

# For local development
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)), debug=True) 