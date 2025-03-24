import os
from backend.app import create_app

# Create the application using the factory function
app = create_app()

# Run the app when executed directly
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)), debug=True) 