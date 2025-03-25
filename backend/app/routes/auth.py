"""
Authentication routes for the Collection Manager application.
Handles user registration, login, logout, and password reset functionality.
"""

import uuid
import bcrypt
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, make_response
from backend.app.config.bigquery import get_bigquery_client, BQ_USERS_TABLE
from google.cloud import bigquery

# Initialize Blueprint for authentication routes
auth_blueprint = Blueprint("auth", __name__)

def check_password(plain_password, hashed_password):
    """
    Helper function to verify a plain text password against a hashed password.
    Uses bcrypt for secure password comparison.
    
    Args:
        plain_password (str): The plain text password to check
        hashed_password (str): The hashed password to compare against
        
    Returns:
        bool: True if passwords match, False otherwise
    """
    try:
        # First try standard bcrypt comparison
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception as e:
        print(f"[ERROR] Password check error: {str(e)}")
        return False

@auth_blueprint.route("/signup", methods=["POST"])
def signup():
    """
    API endpoint for user registration.
    Creates a new user account with hashed password in BigQuery database.
    
    Expected JSON payload:
    {
        "username": str,
        "email": str,
        "password": str
    }
    """
    data = request.get_json()

    # Extract user info from request
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    # Validate input
    if not username or not email or not password:
        return jsonify({"error": "Missing required fields"}), 400
        
    # Check for duplicate username and email
    client = get_bigquery_client()
    
    # Check if username already exists
    username_check_query = f"""
        SELECT COUNT(*) as count 
        FROM `{BQ_USERS_TABLE}` 
        WHERE LOWER(username) = LOWER(@username)
    """
    username_job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("username", "STRING", username),
        ]
    )
    
    try:
        username_results = client.query(username_check_query, job_config=username_job_config).result()
        username_count = list(username_results)[0].count
        
        if username_count > 0:
            return jsonify({"error": "Username already taken"}), 409
    except Exception as e:
        print(f"[ERROR] Username check error: {str(e)}")
        return jsonify({"error": "Error checking username availability"}), 500
    
    # Check if email already exists
    email_check_query = f"""
        SELECT COUNT(*) as count 
        FROM `{BQ_USERS_TABLE}` 
        WHERE LOWER(email) = LOWER(@email)
    """
    email_job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("email", "STRING", email),
        ]
    )
    
    try:
        email_results = client.query(email_check_query, job_config=email_job_config).result()
        email_count = list(email_results)[0].count
        
        if email_count > 0:
            return jsonify({"error": "Email already registered"}), 409
    except Exception as e:
        print(f"[ERROR] Email check error: {str(e)}")
        return jsonify({"error": "Error checking email availability"}), 500

    # Generate unique user_id using UUID
    user_id = str(uuid.uuid4())

    # Hash password using bcrypt
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    # Insert user into BigQuery database
    insert_query = f"""
        INSERT INTO `{BQ_USERS_TABLE}` (user_id, username, email, password)
        VALUES (@user_id, @username, @email, @password)
    """
    insert_job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
            bigquery.ScalarQueryParameter("username", "STRING", username),
            bigquery.ScalarQueryParameter("email", "STRING", email),
            bigquery.ScalarQueryParameter("password", "STRING", hashed_password),
        ]
    )
    try:
        query_job = client.query(insert_query, job_config=insert_job_config)
        query_job.result()  # Ensure execution
        return jsonify({"message": "User registered successfully"}), 201
    except Exception as e:
        print("[ERROR] BigQuery INSERT Error:", str(e))  # Debugging info
        return jsonify({"error": "Failed to register user", "details": str(e)}), 500

@auth_blueprint.route("/login", methods=["POST"])
def login():
    """
    API endpoint for user authentication.
    Supports login with either username or email.
    Creates a session and sets necessary cookies upon successful login.
    
    Expected JSON payload:
    {
        "username": str,  # Can be username or email
        "password": str
    }
    """
    print("[DEBUG] /login POST triggered")
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    # Validate input
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    # Determine if input is email or username
    is_email = '@' in username
    
    # Query BigQuery database based on input type
    client = get_bigquery_client()
    
    # Adjust query based on whether input looks like an email or username
    if is_email:
        query = f"SELECT * FROM `{BQ_USERS_TABLE}` WHERE email = @identifier"
        print(f"[DEBUG] Querying user table for email: {username}")
    else:
        query = f"SELECT * FROM `{BQ_USERS_TABLE}` WHERE username = @identifier"
        print(f"[DEBUG] Querying user table for username: {username}")
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("identifier", "STRING", username),
        ]
    )

    try:
        results = client.query(query, job_config=job_config).result()
        users = list(results)
        
        if not users:
            print(f"[DEBUG] No user found with identifier: {username}")
            return jsonify({"error": "Invalid credentials"}), 401
            
        user = users[0]
        
        # Verify password using password_util
        stored_password = user.password
        print(f"[DEBUG] Retrieved hashed password from DB")
        
        if not check_password(password, stored_password):
            print(f"[DEBUG] Password verification failed")
            return jsonify({"error": "Invalid credentials"}), 401
            
        print(f"[DEBUG] Password verified successfully for user with ID: {user.user_id}")
        
        # Get user_id from the result
        user_id = user.user_id
        username = user.username  # Use the actual username from the DB
        print(f"[DEBUG] User ID: {user_id}, Username: {username}")

        # Create response with user data
        response = make_response(jsonify({
            "message": "Login successful",
            "user_id": user_id,
            "username": username
        }))

        # Store user data in session (no sensitive data)
        session.clear()
        session['user_id'] = user_id
        session['username'] = username
        session.modified = True
        
        # Set session cookie with appropriate security settings
        max_age = 86400  # 24 hours
        response.set_cookie(
            'user_session', 
            str(user_id),
            max_age=max_age,
            path='/',
            httponly=True,
            secure=False,
            samesite=None
        )
        
        # Log the session state for debugging
        print(f"[DEBUG] Session after login: {dict(session)}")
        print(f"[DEBUG] Cookies set: {response.headers.get('Set-Cookie')}")
        
        return response, 200
    except Exception as e:
        print(f"[ERROR] Login error: {str(e)}")
        return jsonify({"error": "An error occurred during login"}), 500

@auth_blueprint.route("/logout", methods=["GET"])
def logout():
    """
    Endpoint to handle user logout.
    Clears the session and removes authentication cookies.
    """
    # Clear the session
    session.clear()
    
    # Create response object for the redirect
    response = make_response(redirect(url_for('home')))
    
    # Remove the user_session cookie
    response.delete_cookie('user_session', path='/')
    
    return response

@auth_blueprint.route("/login", methods=["GET"])
def login_page():
    """Render the login page template."""
    return render_template("login.html")

@auth_blueprint.route("/signup", methods=["GET"])
def signup_page():
    """Render the signup page template."""
    return render_template("signup.html")

@auth_blueprint.route("/reset-password", methods=["GET"])
def reset_password_page():
    """Render the password reset request page template."""
    return render_template("reset_password.html")

@auth_blueprint.route("/request-reset", methods=["POST"])
def request_reset():
    """
    API endpoint for initiating password reset process.
    In a production environment, this would send a reset link via email.
    
    Expected JSON payload:
    {
        "email": str
    }
    """
    data = request.get_json()
    email = data.get("email")
    
    if not email:
        return jsonify({"error": "Email is required"}), 400
    
    # Check if the email exists in the database
    client = get_bigquery_client()
    query = f"SELECT * FROM `{BQ_USERS_TABLE}` WHERE email = @email"
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("email", "STRING", email),
        ]
    )
    
    try:
        results = client.query(query, job_config=job_config).result()
        users = list(results)
        
        # Always return success, even if email not found (security best practice)
        # In a real implementation, you would send an email with a reset token
        reset_token = str(uuid.uuid4())
        
        # For demo purposes, we'll return the token directly
        # In production, this would be sent via email and not exposed in API response
        return jsonify({
            "message": "If your email is registered, you will receive a password reset link shortly.",
            "debug_token": reset_token  # Only for demo - remove in production
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Password reset request error: {str(e)}")
        return jsonify({"error": "An error occurred processing your request"}), 500

@auth_blueprint.route("/confirm-reset", methods=["POST"])
def confirm_reset():
    """
    API endpoint for confirming password reset.
    In a production environment, this would verify a reset token.
    
    Expected JSON payload:
    {
        "token": str,
        "new_password": str
    }
    """
    data = request.get_json()
    token = data.get("token")
    new_password = data.get("new_password")
    
    if not token or not new_password:
        return jsonify({"error": "Token and new password are required"}), 400
    
    # In a real implementation, you would verify the token from a database
    # For demo purposes, we'll simulate a successful reset
    try:
        # Hash the new password
        hashed_password = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        
        # In a real implementation, you would update the user's password in the database
        # using the token to identify the user
        
        return jsonify({
            "message": "Password has been reset successfully"
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Password reset confirmation error: {str(e)}")
        return jsonify({"error": "An error occurred processing your request"}), 500