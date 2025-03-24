import os
from flask import Flask, render_template, jsonify, Blueprint, redirect, url_for, request, session, send_from_directory
from flask_session import Session
import json
import tempfile

# Create session directory in /tmp which is writable in App Engine
session_dir = os.path.join(tempfile.gettempdir(), 'flask_session')
os.makedirs(session_dir, exist_ok=True)

# Create a simple Flask app
app = Flask(__name__, 
            template_folder=os.path.join(os.path.dirname(__file__), 'capstone_frontend_karim', 'templates'),
            static_folder=os.path.join(os.path.dirname(__file__), 'capstone_frontend_karim', 'static'))

# Configure app settings
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = session_dir
app.config['SESSION_USE_SIGNER'] = False
app.config['SESSION_PERMANENT'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour
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

# API routes for collection data
@app.route('/api/collection/items', methods=['GET'])
def get_collection_items():
    """API endpoint to get items in a collection"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Mock collection items data
    collection_name = request.args.get('collection_name', '')
    items = [
        {
            'item_id': f'item{i}',
            'name': f'Sample Item {i}',
            'description': f'This is a sample item {i} in {collection_name}',
            'value': i * 100,
            'date_added': '2025-03-24'
        } for i in range(1, 6)
    ]
    
    return jsonify({'items': items})

@app.route('/api/collection/stats', methods=['GET'])
def get_collection_stats():
    """API endpoint to get collection statistics"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Mock collection stats
    stats = {
        'total_value': 1500,
        'total_items': 8,
        'collections': 2,
        'recent_items': 3
    }
    
    return jsonify(stats)

@app.route('/api/collection/list', methods=['GET'])
def get_collections():
    """API endpoint to get all collections"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Mock collections data
    collections = [
        {'collection_name': 'Sample Collection', 'total_items': 5},
        {'collection_name': 'Demo Items', 'total_items': 3}
    ]
    
    return jsonify({'collections': collections})

# Additional API routes for collection management
@app.route('/api/collection/create', methods=['POST'])
def create_collection():
    """API endpoint to create a new collection"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Mock collection creation
    try:
        data = request.get_json() if request.is_json else request.form
        collection_name = data.get('collection_name', '')
        
        if not collection_name:
            return jsonify({'success': False, 'message': 'Collection name is required'}), 400
            
        return jsonify({'success': True, 'message': f'Collection {collection_name} created'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/api/collection/add_item', methods=['POST'])
def add_item():
    """API endpoint to add an item to a collection"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Mock item addition
    try:
        data = request.get_json() if request.is_json else request.form
        collection_name = data.get('collection_name', '')
        item_name = data.get('name', '')
        
        if not collection_name or not item_name:
            return jsonify({'success': False, 'message': 'Collection name and item name are required'}), 400
            
        return jsonify({
            'success': True, 
            'message': f'Item {item_name} added to {collection_name}',
            'item_id': f'item{hash(item_name) % 1000}'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/api/collection/remove_item', methods=['POST'])
def remove_item():
    """API endpoint to remove an item from a collection"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Mock item removal
    try:
        data = request.get_json() if request.is_json else request.form
        item_id = data.get('item_id', '')
        
        if not item_id:
            return jsonify({'success': False, 'message': 'Item ID is required'}), 400
            
        return jsonify({'success': True, 'message': f'Item {item_id} removed'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

# Run the app when executed directly
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)), debug=True) 