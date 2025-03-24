"""
Main Flask application module for the Collection Manager application.
This module handles the core application setup, configuration, and routing.
"""

import os
import tempfile
from datetime import timedelta
from flask import Flask, render_template, session, redirect, url_for, request, make_response
from flask_session import Session
from app.routes.auth import auth_blueprint
from app.routes.collection import collection_blueprint
from app.utils.token_blocklist import is_token_revoked
from app.config.bigquery import get_bigquery_client, BQ_COLLECTION_ITEMS_TABLE, BQ_USERS_TABLE
from google.cloud import bigquery
from app.utils.decorators import login_required
import logging
import sys

def create_app():
    """
    Factory function to create and configure the Flask application.
    Sets up all necessary configurations, middleware, and routes.
    """
    # Set up logging
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    logging.info("Starting application initialization")
    
    try:
        # Calculate absolute paths for template and static directories
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_dir = os.path.join(base_dir, "capstone_frontend_karim", "templates")
        static_dir = os.path.join(base_dir, "capstone_frontend_karim", "static")
        
        logging.info(f"Base directory: {base_dir}")
        logging.info(f"Template directory: {template_dir}")
        logging.info(f"Static directory: {static_dir}")
        
        # Check if directories exist
        logging.info(f"Template dir exists: {os.path.exists(template_dir)}")
        logging.info(f"Static dir exists: {os.path.exists(static_dir)}")
        
        # Create a temporary directory for storing session files
        session_dir = os.path.join(tempfile.gettempdir(), 'flask_session')
        os.makedirs(session_dir, exist_ok=True)
        logging.info(f"Session directory: {session_dir}")

        # Initialize Flask application with custom template and static directories
        app = Flask(__name__, 
                    template_folder=template_dir,
                    static_folder=static_dir)
        logging.info("Flask app initialized")
        app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")  # Use environment variable for secret key

        # Configure session settings for better browser compatibility
        # These settings are particularly important for Safari browser support
        app.config['SESSION_COOKIE_SECURE'] = False  # Must be False for HTTP
        app.config['SESSION_COOKIE_HTTPONLY'] = True
        app.config['SESSION_COOKIE_SAMESITE'] = None  # Safari might have issues with 'Lax'
        app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # Increase to 24 hours for testing
        
        # Configure session storage to use filesystem for better compatibility
        app.config['SESSION_TYPE'] = 'filesystem'
        app.config['SESSION_FILE_DIR'] = session_dir
        app.config['SESSION_USE_SIGNER'] = False  # Disable signing for compatibility
        Session(app)

        # Add CORS headers to all responses for cross-origin requests
        @app.after_request
        def after_request(response):
            response.headers.add('Access-Control-Allow-Origin', '*')
            response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
            response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
            return response

        # Configure session handling before each request
        @app.before_request
        def before_request():
            session.permanent = True
            # Print debug info about the request
            print(f"[DEBUG] Request from: {request.user_agent}")
            print(f"[DEBUG] Current session: {dict(session)}")
        
        # Register API blueprints for authentication and collection management
        app.register_blueprint(auth_blueprint, url_prefix="/api/auth")
        app.register_blueprint(collection_blueprint, url_prefix="/api/collection")

        # Frontend Routes
        @app.route("/")
        def home():
            """Render the home page."""
            return render_template("home.html")

        @app.route("/dashboard")
        @login_required
        def dashboard():
            """
            Dashboard route that displays user's collections.
            Requires user authentication and verifies user existence in database.
            """
            print(f"[DEBUG] Dashboard Route - Session data: {dict(session)}")
            print(f"[DEBUG] Dashboard Route - Cookies: {request.cookies}")
            
            # Get user_id from session
            user_id = session.get('user_id')
            
            if not user_id:
                print("[DEBUG] Dashboard Route - No user_id in session, redirecting to login")
                return redirect(url_for("auth.login_page"))
            
            # Verify the user_id exists in the database
            client = get_bigquery_client()
            query = f"""
                SELECT user_id FROM `{BQ_USERS_TABLE}`
                WHERE user_id = @user_id
                LIMIT 1
            """
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
                ]
            )
            
            try:
                results = list(client.query(query, job_config=job_config).result())
                if not results:
                    session.clear()
                    return redirect(url_for("auth.login_page"))
            except Exception as e:
                print(f"[ERROR] Failed to verify user: {str(e)}")
                session.clear()
                return redirect(url_for("auth.login_page"))
            
            print(f"[DEBUG] Dashboard Route - User ID: {user_id}")
            
            # Query to get user's collections with item counts
            query = f"""
                SELECT DISTINCT collection_name, COUNT(*) as total_items
                FROM `{BQ_COLLECTION_ITEMS_TABLE}`
                WHERE user_id = @user_id
                GROUP BY collection_name
            """
            job_config = bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("user_id", "STRING", user_id)]
            )
            
            try:
                query_job = client.query(query, job_config=job_config)
                collections = list(query_job)
                print(f"[DEBUG] Dashboard Route - Retrieved {len(collections)} collections")
                return render_template("dashboard.html", username=session.get("username"), collections=collections)
            except Exception as e:
                print(f"[DEBUG] Dashboard Route - Error: {str(e)}")
                return render_template("dashboard.html", username=session.get("username"), collections=[])

        @app.route("/about")
        def about():
            """Render the about page."""
            return render_template("about.html")

        @app.route("/contact")
        def contact():
            """Render the contact page."""
            return render_template("contact.html")

        return app
    except Exception as e:
        print(f"Error starting server: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    create_app()