import os
from flask import Flask, render_template, jsonify, Blueprint, redirect, url_for, request, session

# Create a simple Flask app
app = Flask(__name__, 
            template_folder=os.path.join(os.path.dirname(__file__), 'capstone_frontend_karim', 'templates'),
            static_folder=os.path.join(os.path.dirname(__file__), 'capstone_frontend_karim', 'static'))

# Configure app settings
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")
app.config['SESSION_TYPE'] = 'filesystem'

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
    # Simple mock login
    username = request.form.get('username')
    if username:
        session['user_id'] = 'test-user-id'
        session['username'] = username
        return redirect(url_for('dashboard'))
    return redirect(url_for('auth.login_page'))

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
        return render_template('dashboard.html', username=session.get('username'), collections=[])
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