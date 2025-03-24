import os
from flask import Flask, render_template, jsonify, Blueprint, redirect, url_for, request, session, send_from_directory
from flask_session import Session
import json

# Create a simple Flask app
app = Flask(__name__, 
            template_folder=os.path.join(os.path.dirname(__file__), 'capstone_frontend_karim', 'templates'),
            static_folder=os.path.join(os.path.dirname(__file__), 'capstone_frontend_karim', 'static'))

# Configure app settings
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Create an auth blueprint
auth_blueprint = Blueprint('auth', __name__)

@auth_blueprint.route('/login')
def login_page():
    return render_template('login.html')

@auth_blueprint.route('/signup')
def signup_page():
    return render_template('signup.html')

@auth_blueprint.route('/login', methods=['POST'])
def login():
    # Handle AJAX login (the client is expecting JSON)
    try:
        if request.is_json:
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
        else:
            username = request.form.get('username')
            password = request.form.get('password')
        
        if username and password:  # Very simple validation
            session['user_id'] = 'test-user-id'
            session['username'] = username
            return jsonify({'success': True, 'redirect': url_for('dashboard')})
        else:
            return jsonify({'success': False, 'message': 'Invalid credentials'})
    except Exception as e:
        print(f"Login error: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@auth_blueprint.route('/signup', methods=['POST'])
def signup():
    # Handle AJAX signup
    try:
        if request.is_json:
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
        else:
            username = request.form.get('username')
            password = request.form.get('password')
        
        if username and password:  # Very simple validation
            # In a real app, you'd create a user in the database here
            session['user_id'] = 'new-test-user'
            session['username'] = username
            return jsonify({'success': True, 'redirect': url_for('dashboard')})
        else:
            return jsonify({'success': False, 'message': 'Missing username or password'})
    except Exception as e:
        print(f"Signup error: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@auth_blueprint.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# Register the auth blueprint
app.register_blueprint(auth_blueprint, url_prefix='/api/auth')

# Basic routes
@app.route('/')
def home():
    try:
        return render_template('home.html')
    except Exception as e:
        return f"Error rendering template: {str(e)}", 500

# Special route for images that may be referenced directly
@app.route('/images/<path:filename>')
def serve_image(filename):
    try:
        return send_from_directory(os.path.join(app.static_folder, 'images'), filename)
    except Exception as e:
        return f"Image not found: {str(e)}", 404

@app.route('/about')
def about():
    try:
        return render_template('about.html')
    except Exception as e:
        return f"Error rendering template: {str(e)}", 500

@app.route('/dashboard')
def dashboard():
    try:
        if 'user_id' not in session:
            return redirect(url_for('auth.login_page'))
        # Mock collections data
        collections = [
            {'collection_name': 'Sample Collection', 'total_items': 5},
            {'collection_name': 'Demo Items', 'total_items': 3}
        ]
        return render_template('dashboard.html', username=session.get('username'), collections=collections)
    except Exception as e:
        return f"Error rendering dashboard: {str(e)}", 500

@app.route('/contact')
def contact():
    try:
        return render_template('contact.html')
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