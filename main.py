import os
from flask import Flask, render_template, jsonify

# Create a simple Flask app
app = Flask(__name__, 
            template_folder=os.path.join(os.path.dirname(__file__), 'capstone_frontend_karim', 'templates'),
            static_folder=os.path.join(os.path.dirname(__file__), 'capstone_frontend_karim', 'static'))

# Configure app settings
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")

# Basic routes
@app.route('/')
def home():
    try:
        return render_template('home.html')
    except Exception as e:
        return f"Error rendering template: {str(e)}", 500

@app.route('/about')
def about():
    try:
        return render_template('about.html')
    except Exception as e:
        return f"Error rendering template: {str(e)}", 500

@app.route('/api/health')
def health():
    return jsonify({
        'status': 'ok',
        'message': 'App is running',
        'environment': os.getenv('FLASK_ENV', 'unknown')
    })

# Run the app when executed directly
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)), debug=True) 