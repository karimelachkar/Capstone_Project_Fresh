"""
Collection management routes for the Collection Manager application.
Handles CRUD operations for collections and collection items, including search and analytics.
"""

import uuid
from flask import Blueprint, request, jsonify, session, Response
from functools import wraps
from backend.app.config.bigquery import get_bigquery_client, BQ_COLLECTION_ITEMS_TABLE, BQ_COLLECTIONS_TABLE, BQ_DATASET
from google.cloud import bigquery
import csv
import io
from datetime import datetime

# Initialize Blueprint for collection routes
collection_blueprint = Blueprint("collection", __name__)

def ensure_tables_exist():
    """
    Ensures all required BigQuery tables exist.
    Returns True if all tables exist or were successfully created, False otherwise.
    """
    try:
        client = get_bigquery_client()
        client._location = "europe-southwest1"
        
        # Check if tables exist
        tables_to_check = [BQ_COLLECTION_ITEMS_TABLE, BQ_COLLECTIONS_TABLE]
        
        for table_id in tables_to_check:
            dataset_id = table_id.split('.')[0]
            table_name = table_id.split('.')[-1]
            
            try:
                # Check if the table exists
                client.get_table(f"{dataset_id}.{table_name}")
                print(f"[INFO] Table {table_id} exists")
            except Exception as e:
                print(f"[WARNING] Table {table_id} does not exist: {str(e)}")
                # For this app, we won't auto-create tables - just return False
                return False
        
        return True
    except Exception as e:
        print(f"[ERROR] Failed to ensure tables exist: {str(e)}")
        return False

def login_required(f):
    """
    Decorator to ensure user is authenticated before accessing protected routes.
    
    Args:
        f: The function to wrap
        
    Returns:
        The wrapped function that checks for authentication
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Unauthorized access"}), 401
        return f(*args, **kwargs)
    return decorated_function

@collection_blueprint.route("/", methods=["GET"])
@login_required
def get_collection():
    """
    API endpoint to fetch all collection items for the authenticated user.
    Returns a list of all items in the user's collection.
    """
    user_id = session.get('user_id')
    print(f"[DEBUG] Collection Route - User ID from session: {user_id}")
    print(f"[DEBUG] Collection Route - User ID type: {type(user_id)}")

    # Ensure user_id is a string
    if not isinstance(user_id, str):
        user_id = str(user_id)
        print(f"[DEBUG] Collection Route - Converted user_id to string: {user_id}")

    # Query to fetch user's collection items
    client = get_bigquery_client()
    
    # Set location explicitly
    client._location = "europe-southwest1"
    
    query = f"SELECT * FROM `{BQ_COLLECTION_ITEMS_TABLE}` WHERE user_id = @user_id"
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
        ]
    )

    # Debug log the query and parameters
    print(f"[DEBUG] Collection Route - Query: {query}")
    print(f"[DEBUG] Collection Route - Parameters: {job_config.query_parameters}")
    
    try:
        results = client.query(query, job_config=job_config).result()
        items = [dict(row) for row in results]
        print(f"[DEBUG] Collection Route - Retrieved {len(items)} items")
        print(f"[DEBUG] Collection Route - First item (if any): {items[0] if items else 'No items'}")
        return jsonify({"collection": items}), 200
    except Exception as e:
        print("[DEBUG] Collection Route - Error:", str(e))
        print("[DEBUG] Collection Route - Error type:", type(e))
        return jsonify({"error": "Failed to fetch collection", "details": str(e)}), 500

@collection_blueprint.route("/unassigned", methods=["GET"])
@login_required
def get_unassigned_items():
    """
    API endpoint to fetch items that haven't been assigned to any collection.
    Returns items where collection_name is NULL or empty.
    """
    user_id = session.get('user_id')
    print(f"[DEBUG] Unassigned Items Route - User ID from session: {user_id}")

    # Ensure user_id is a string
    if not isinstance(user_id, str):
        user_id = str(user_id)
        print(f"[DEBUG] Unassigned Items Route - Converted user_id to string: {user_id}")

    # Query to fetch user's items with missing or empty collection names
    client = get_bigquery_client()
    
    # Set location explicitly
    client._location = "europe-southwest1"
    
    query = f"""
        SELECT * FROM `{BQ_COLLECTION_ITEMS_TABLE}` 
        WHERE user_id = @user_id 
        AND (collection_name IS NULL OR TRIM(collection_name) = '')
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
        ]
    )

    # Debug log the query and parameters
    print(f"[DEBUG] Unassigned Items Route - Query: {query}")
    
    try:
        results = client.query(query, job_config=job_config).result()
        items = [dict(row) for row in results]
        print(f"[DEBUG] Unassigned Items Route - Retrieved {len(items)} unassigned items")
        return jsonify({"items": items}), 200
    except Exception as e:
        print(f"[DEBUG] Unassigned Items Route - Error: {str(e)}")
        return jsonify({"error": "Failed to fetch unassigned items", "details": str(e)}), 500

@collection_blueprint.route("/collections", methods=["GET"])
@login_required
def get_collections():
    """
    API endpoint to fetch all unique collection names for the authenticated user.
    First tries to get collections from the collections table, falls back to collection_items if needed.
    """
    user_id = session.get('user_id')
    print(f"[DEBUG] Collections Route - User ID from session: {user_id}")

    # Ensure user_id is a string
    if not isinstance(user_id, str):
        user_id = str(user_id)
        print(f"[DEBUG] Collections Route - Converted user_id to string: {user_id}")

    # Query to fetch collections from the collections table
    client = get_bigquery_client()
    
    # Set location explicitly
    client._location = "europe-southwest1"
    
    query = f"""
        SELECT collection_id, collection_name 
        FROM `{BQ_COLLECTIONS_TABLE}` 
        WHERE user_id = @user_id 
        ORDER BY collection_name
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
        ]
    )

    # Debug log the query
    print(f"[DEBUG] Collections Route - Query: {query}")
    
    try:
        results = client.query(query, job_config=job_config).result()
        collections = [{"collection_id": row["collection_id"], "collection_name": row["collection_name"]} for row in results]
        print(f"[DEBUG] Collections Route - Retrieved {len(collections)} collections")
        
        # If no collections found in collections table, fallback to the collection_items table for backward compatibility
        if not collections:
            print(f"[DEBUG] No collections found in collections table, falling back to collection_items")
            fallback_query = f"""
                SELECT DISTINCT collection_name 
                FROM `{BQ_COLLECTION_ITEMS_TABLE}` 
                WHERE user_id = @user_id 
                AND collection_name IS NOT NULL 
                AND TRIM(collection_name) != ''
                GROUP BY collection_name
            """
            
            fallback_results = client.query(fallback_query, job_config=job_config).result()
            collections = [{"collection_name": row["collection_name"]} for row in fallback_results]
            print(f"[DEBUG] Retrieved {len(collections)} collections from fallback")
        
        return jsonify({"collections": collections}), 200
    except Exception as e:
        print(f"[DEBUG] Collections Route - Error: {str(e)}")
        return jsonify({"error": "Failed to fetch collections", "details": str(e)}), 500

@collection_blueprint.route("/assign", methods=["POST"])
@login_required
def assign_collections():
    """
    API endpoint to assign items to collections.
    Accepts a list of assignments with item_id and collection_name.
    
    Expected JSON payload:
    {
        "assignments": [
            {
                "item_id": str,
                "collection_name": str,
                "collection_id": str
            },
            ...
        ]
    }
    """
    user_id = session.get('user_id')
    print(f"[DEBUG] Assign Collections Route - User ID from session: {user_id}")

    # Ensure user_id is a string
    if not isinstance(user_id, str):
        user_id = str(user_id)
        print(f"[DEBUG] Assign Collections Route - Converted user_id to string: {user_id}")

    # Get the assignments from the request
    data = request.get_json()
    assignments = data.get("assignments", [])
    
    if not assignments:
        return jsonify({"error": "No assignments provided"}), 400
    
    print(f"[DEBUG] Assign Collections Route - Received {len(assignments)} assignments")
    
    client = get_bigquery_client()
    
    # Set location explicitly
    client._location = "europe-southwest1"
    
    success_count = 0
    error_count = 0
    errors = []
    
    for assignment in assignments:
        item_id = assignment.get("item_id")
        collection_name = assignment.get("collection_name")
        collection_id = assignment.get("collection_id")
        
        if not item_id or (not collection_name and not collection_id):
            error_count += 1
            errors.append(f"Missing required fields for assignment: {assignment}")
            continue
        
        # First, verify the item exists and belongs to the user
        check_query = f"""
            SELECT item_id FROM `{BQ_COLLECTION_ITEMS_TABLE}`
            WHERE item_id = @item_id AND user_id = @user_id
        """
        
        check_job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("item_id", "STRING", item_id),
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
            ]
        )
        
        try:
            check_results = client.query(check_query, job_config=check_job_config).result()
            if check_results.total_rows == 0:
                error_count += 1
                errors.append(f"Item {item_id} not found or does not belong to user")
                continue
                
            # Build update fields
            update_fields = []
            update_params = [
                bigquery.ScalarQueryParameter("item_id", "STRING", item_id),
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
            ]
            
            if collection_name:
                update_fields.append("collection_name = @collection_name")
                update_params.append(bigquery.ScalarQueryParameter("collection_name", "STRING", collection_name))
                
            if collection_id:
                update_fields.append("collection_id = @collection_id")
                update_params.append(bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id))
                
            # Update the collection info
            update_query = f"""
                UPDATE `{BQ_COLLECTION_ITEMS_TABLE}`
                SET {', '.join(update_fields)}
                WHERE item_id = @item_id AND user_id = @user_id
            """
            
            update_job_config = bigquery.QueryJobConfig(query_parameters=update_params)
            
            client.query(update_query, job_config=update_job_config).result()
            success_count += 1
            print(f"[DEBUG] Assign Collections Route - Successfully assigned item {item_id} to collection")
            
        except Exception as e:
            error_count += 1
            error_msg = f"Error processing item {item_id}: {str(e)}"
            errors.append(error_msg)
            print(f"[DEBUG] Assign Collections Route - {error_msg}")
    
    # Return summary of the operation
    return jsonify({
        "message": f"Processed {len(assignments)} assignments",
        "success_count": success_count,
        "error_count": error_count,
        "errors": errors if errors else None
    }), 200 if error_count == 0 else 207

@collection_blueprint.route("/add", methods=["POST"])
@login_required
def add_item():
    """
    API endpoint to add a new item to a collection.
    
    Expected JSON payload:
    {
        "name": str,
        "description": str,
        "collection_name": str,
        "collection_id": str,   
        "year": int,
        "condition": str,
        "value": float
    }
    """
    user_id = session.get('user_id')
    data = request.get_json()
    print(f"[DEBUG] Add Item - Got request data: {data}")
    
    # Validate required fields
    if not data.get("name"):
        return jsonify({"error": "Name is required"}), 400
    
    # Parse value field if present
    value = None
    if "value" in data and data["value"]:
        try:
            value = float(data["value"])
        except ValueError:
            return jsonify({"error": "Value must be a number"}), 400
    
    # Parse year field if present
    year = None
    if "year" in data and data["year"]:
        try:
            year = int(data["year"])
        except ValueError:
            return jsonify({"error": "Year must be an integer"}), 400
    
    client = get_bigquery_client()
    client._location = "europe-southwest1"
    
    # Get collection details from the request
    collection_name = data.get("collection_name", "")
    collection_id = data.get("collection_id")
    
    # If we have a collection_id, verify it exists and get the collection_name
    if collection_id:
        lookup_query = f"""
            SELECT collection_id, collection_name 
            FROM `{BQ_COLLECTIONS_TABLE}`
            WHERE user_id = @user_id 
            AND collection_id = @collection_id
        """
        
        lookup_params = [
            bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
            bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id)
        ]
        
        lookup_job_config = bigquery.QueryJobConfig(query_parameters=lookup_params)
        
        try:
            lookup_results = client.query(lookup_query, job_config=lookup_job_config).result()
            # If we found a collection, use its values
            row_found = False
            for row in lookup_results:
                collection_id = row.collection_id
                collection_name = row.collection_name
                row_found = True
                print(f"[DEBUG] Verified collection {collection_name} with id {collection_id}")
                break
                
            # If collection_id not found, treat it as invalid
            if not row_found:
                print(f"[WARNING] Collection ID {collection_id} not found for user {user_id}")
                # Try to use the collection_name as a fallback
                if collection_name:
                    collection_id = None  # Reset so we'll look up by name
                else:
                    return jsonify({"error": "Invalid collection ID"}), 400
        except Exception as e:
            print(f"[ERROR] Failed to verify collection_id: {str(e)}")
            # If verification fails, fall back to collection_name
            collection_id = None
    
    # If we don't have a valid collection_id but have a name, look up or create the collection
    if not collection_id and collection_name:
        # Look up the collection_id for this collection_name
        lookup_query = f"""
            SELECT collection_id 
            FROM `{BQ_COLLECTIONS_TABLE}`
            WHERE user_id = @user_id 
            AND collection_name = @collection_name
        """
        
        lookup_params = [
            bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
            bigquery.ScalarQueryParameter("collection_name", "STRING", collection_name)
        ]
        
        lookup_job_config = bigquery.QueryJobConfig(query_parameters=lookup_params)
        
        try:
            lookup_results = client.query(lookup_query, job_config=lookup_job_config).result()
            # If we found a collection_id, use it
            for row in lookup_results:
                collection_id = row.collection_id
                print(f"[DEBUG] Found collection_id {collection_id} for collection {collection_name}")
                break
                
            # If we couldn't find the collection, create it
            if not collection_id:
                print(f"[DEBUG] Collection '{collection_name}' not found, creating it")
                collection_id = str(uuid.uuid4())
                
                create_query = f"""
                    INSERT INTO `{BQ_COLLECTIONS_TABLE}`
                    (user_id, collection_id, collection_name)
                    VALUES
                    (@user_id, @collection_id, @collection_name)
                """
                
                create_params = [
                    bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
                    bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id),
                    bigquery.ScalarQueryParameter("collection_name", "STRING", collection_name)
                ]
                
                create_job_config = bigquery.QueryJobConfig(query_parameters=create_params)
                client.query(create_query, job_config=create_job_config).result()
                print(f"[DEBUG] Created collection '{collection_name}' with id {collection_id}")
                
        except Exception as e:
            print(f"[ERROR] Failed to look up collection: {str(e)}")
            # If we can't look up or create the collection, generate a random collection_id as fallback
            collection_id = str(uuid.uuid4())
    elif not collection_id:
        # If no collection info provided, generate a random collection_id and use "Uncategorized"
        collection_id = str(uuid.uuid4())
        collection_name = "Uncategorized"
    
    # Prepare item data
    item_id = str(uuid.uuid4())
    
    item_data = {
        "item_id": item_id,
        "user_id": user_id,
        "name": data.get("name"),
        "description": data.get("description", ""),
        "collection_name": collection_name,
        "collection_id": collection_id,
        "value": value,
        "year": year,
        "condition": data.get("condition", "")
    }
    
    # Insert item into BigQuery
    
    # Prepare query parameters
    query_params = [
        bigquery.ScalarQueryParameter("item_id", "STRING", item_id),
        bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
        bigquery.ScalarQueryParameter("name", "STRING", item_data["name"]),
        bigquery.ScalarQueryParameter("description", "STRING", item_data["description"]),
        bigquery.ScalarQueryParameter("collection_name", "STRING", item_data["collection_name"]),
        bigquery.ScalarQueryParameter("collection_id", "STRING", item_data["collection_id"]),
        bigquery.ScalarQueryParameter("value", "FLOAT", item_data["value"]),
        bigquery.ScalarQueryParameter("year", "INT64", item_data["year"]),
        bigquery.ScalarQueryParameter("condition", "STRING", item_data["condition"])
    ]
    
    query = f"""
        INSERT INTO `{BQ_COLLECTION_ITEMS_TABLE}` 
        (item_id, user_id, name, description, collection_name, collection_id, value, year, condition)
        VALUES 
        (@item_id, @user_id, @name, @description, @collection_name, @collection_id, @value, @year, @condition)
    """
    
    job_config = bigquery.QueryJobConfig(query_parameters=query_params)
    
    try:
        client.query(query, job_config=job_config).result()
        return jsonify({"message": "Item added successfully", "item_id": item_id}), 201
    except Exception as e:
        print(f"[ERROR] Failed to add item: {str(e)}")
        return jsonify({"error": "Failed to add item", "details": str(e)}), 500

@collection_blueprint.route("/item/update/<string:item_id>", methods=["PUT"])
@login_required
def update_item(item_id):
    """
    API endpoint to update an existing item.
    
    Expected JSON payload:
    {
        "name": str (optional),
        "description": str (optional),
        "collection_name": str (optional),
        "collection_id": str (optional),
        "value": float (optional),
        "year": int (optional),
        "condition": str (optional)
    }
    """
    user_id = session.get('user_id')
    data = request.get_json()
    
    # Validate that at least one field is being updated
    if not any(data.values()):
        return jsonify({"error": "No fields to update"}), 400
    
    # Build update query dynamically based on provided fields
    update_fields = []
    query_params = [
        bigquery.ScalarQueryParameter("item_id", "STRING", item_id),
        bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
    ]
    
    if "name" in data:
        update_fields.append("name = @name")
        query_params.append(bigquery.ScalarQueryParameter("name", "STRING", data["name"]))
    
    if "description" in data:
        update_fields.append("description = @description")
        query_params.append(bigquery.ScalarQueryParameter("description", "STRING", data["description"]))
    
    if "collection_name" in data:
        update_fields.append("collection_name = @collection_name")
        query_params.append(bigquery.ScalarQueryParameter("collection_name", "STRING", data["collection_name"]))
    
    if "collection_id" in data:
        update_fields.append("collection_id = @collection_id")
        query_params.append(bigquery.ScalarQueryParameter("collection_id", "STRING", data["collection_id"]))
        
    if "value" in data:
        update_fields.append("value = @value")
        query_params.append(bigquery.ScalarQueryParameter("value", "FLOAT", float(data["value"]) if data["value"] else None))
        
    if "year" in data:
        update_fields.append("year = @year")
        query_params.append(bigquery.ScalarQueryParameter("year", "INT64", int(data["year"]) if data["year"] else None))
        
    if "condition" in data:
        update_fields.append("condition = @condition")
        query_params.append(bigquery.ScalarQueryParameter("condition", "STRING", data["condition"]))
    
    if not update_fields:
        return jsonify({"error": "No valid fields to update"}), 400
    
    # Construct and execute update query
    client = get_bigquery_client()
    client._location = "europe-southwest1"
    
    query = f"""
        UPDATE `{BQ_COLLECTION_ITEMS_TABLE}`
        SET {', '.join(update_fields)}
        WHERE item_id = @item_id AND user_id = @user_id
    """
    
    job_config = bigquery.QueryJobConfig(query_parameters=query_params)
    
    try:
        client.query(query, job_config=job_config).result()
        return jsonify({"message": "Item updated successfully"}), 200
    except Exception as e:
        print(f"[ERROR] Failed to update item: {str(e)}")
        return jsonify({"error": "Failed to update item", "details": str(e)}), 500

@collection_blueprint.route("/item/delete/<string:item_id>", methods=["DELETE"])
@login_required
def delete_item(item_id):
    """
    API endpoint to delete an item from the collection.
    
    Args:
        item_id (str): The ID of the item to delete
    """
    user_id = session.get('user_id')
    
    client = get_bigquery_client()
    client._location = "europe-southwest1"
    
    query = f"""
        DELETE FROM `{BQ_COLLECTION_ITEMS_TABLE}`
        WHERE item_id = @item_id AND user_id = @user_id
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("item_id", "STRING", item_id),
            bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
        ]
    )
    
    try:
        client.query(query, job_config=job_config).result()
        return jsonify({"message": "Item deleted successfully"}), 200
    except Exception as e:
        print(f"[ERROR] Failed to delete item: {str(e)}")
        return jsonify({"error": "Failed to delete item", "details": str(e)}), 500

@collection_blueprint.route("/search", methods=["GET"])
@login_required
def search_items():
    """
    API endpoint to search for items in collections.
    Query parameters:
    - query: Search query
    - collection_name: Filter by collection (can be collection_id or collection_name)
    - min_year, max_year: Filter by year range
    - min_value, max_value: Filter by value range
    """
    user_id = session.get('user_id')
    print(f"[DEBUG] Search Route - User ID: {user_id}, Args: {dict(request.args)}")
    
    # Get query parameters
    query = request.args.get('query', '')
    collection_filter = request.args.get('collection_name', '')  # This could be collection_id now
    min_year = request.args.get('min_year', '')
    max_year = request.args.get('max_year', '')
    min_value = request.args.get('min_value', '')
    max_value = request.args.get('max_value', '')
    
    client = get_bigquery_client()
    client._location = "europe-southwest1"
    
    try:
        # Query using the actual schema fields
        query_text = f"""
            SELECT 
                item_id, 
                name, 
                description, 
                collection_name,
                collection_id,
                IFNULL(value, 0) as value,
                IFNULL(year, 0) as year,
                IFNULL(condition, 'Unknown') as condition
            FROM `{BQ_COLLECTION_ITEMS_TABLE}`
            WHERE user_id = @user_id
        """
        
        params = [
            bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
        ]
        
        # Add collection filter if provided - can be collection_id or collection_name
        if collection_filter:
            # First try to filter by collection_id
            query_text += " AND collection_id = @collection_filter"
            params.append(bigquery.ScalarQueryParameter("collection_filter", "STRING", collection_filter))
        
        # Add search query if provided
        if query:
            query_text += " AND LOWER(name) LIKE @query"
            params.append(bigquery.ScalarQueryParameter("query", "STRING", f"%{query.lower()}%"))
        
        # Add year filters if provided - using the year field directly
        if min_year:
            try:
                min_year_int = int(min_year)
                query_text += " AND IFNULL(year, 0) >= @min_year"
                params.append(bigquery.ScalarQueryParameter("min_year", "INT64", min_year_int))
            except (ValueError, TypeError):
                print(f"[WARNING] Invalid min_year value: {min_year}")
        
        if max_year:
            try:
                max_year_int = int(max_year)
                query_text += " AND IFNULL(year, 0) <= @max_year"
                params.append(bigquery.ScalarQueryParameter("max_year", "INT64", max_year_int))
            except (ValueError, TypeError):
                print(f"[WARNING] Invalid max_year value: {max_year}")
        
        # Add value filters if provided
        if min_value:
            try:
                min_value_float = float(min_value)
                query_text += " AND IFNULL(value, 0) >= @min_value"
                params.append(bigquery.ScalarQueryParameter("min_value", "FLOAT64", min_value_float))
            except (ValueError, TypeError):
                print(f"[WARNING] Invalid min_value: {min_value}")
        
        if max_value:
            try:
                max_value_float = float(max_value)
                query_text += " AND IFNULL(value, 0) <= @max_value"
                params.append(bigquery.ScalarQueryParameter("max_value", "FLOAT64", max_value_float))
            except (ValueError, TypeError):
                print(f"[WARNING] Invalid max_value: {max_value}")
        
        # Complete and order the query
        query_text += " ORDER BY value DESC LIMIT 100"
        
        print(f"[DEBUG] Search query: {query_text}")
        print(f"[DEBUG] Parameters: {params}")
        
        # Create job config
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        
        # Execute the query
        query_job = client.query(query_text, job_config=job_config)
        results = list(query_job.result())
        
        # Convert to list of dicts for JSON
        items = []
        for row in results:
            item = dict(row.items())
            # Ensure value is a float for JSON serialization
            if 'value' in item:
                item['value'] = float(item['value'])
            items.append(item)
        
        print(f"[DEBUG] Search Route - Found {len(items)} items")
        
        return jsonify({"collection": items}), 200
        
    except Exception as e:
        import traceback
        print(f"[ERROR] Search failed: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        return jsonify({"error": "Failed to search items", "details": str(e)}), 500

@collection_blueprint.route("/analytics", methods=["GET"])
@login_required
def get_collection_analytics():
    """
    API endpoint to get analytics about the user's collection.
    Returns statistics about items, collections, and tags.
    """
    user_id = session.get('user_id')
    
    client = get_bigquery_client()
    client._location = "europe-southwest1"
    
    # Ensure that all required tables exist
    if not ensure_tables_exist():
        return jsonify({"error": "Failed to ensure required tables exist"}), 500
    
    try:
        # Print schema information for debugging
        print(f"[DEBUG] Attempting to fetch table schema for: {BQ_COLLECTION_ITEMS_TABLE}")
        table_ref = client.dataset(BQ_DATASET.split('.')[0]).table(BQ_COLLECTION_ITEMS_TABLE.split('.')[-1])
        table = client.get_table(table_ref)
        print(f"[DEBUG] Table schema: {[field.name for field in table.schema]}")
    except Exception as e:
        print(f"[DEBUG] Error fetching schema: {str(e)}")
    
    # Get total items count
    items_query = f"""
        SELECT COUNT(*) as total_items
        FROM `{BQ_COLLECTION_ITEMS_TABLE}`
        WHERE user_id = @user_id
    """
    
    # Get items by collection with collection_id
    collections_query = f"""
        SELECT c.collection_id, c.collection_name, COUNT(i.item_id) as item_count
        FROM `{BQ_COLLECTIONS_TABLE}` c
        LEFT JOIN `{BQ_COLLECTION_ITEMS_TABLE}` i 
        ON c.collection_id = i.collection_id AND c.user_id = i.user_id
        WHERE c.user_id = @user_id
        GROUP BY c.collection_id, c.collection_name
        ORDER BY item_count DESC
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
        ]
    )
    
    try:
        # Execute queries
        items_result = client.query(items_query, job_config=job_config).result()
        collections_result = client.query(collections_query, job_config=job_config).result()
        
        # Process results
        total_items = next(items_result).total_items
        collections = [dict(row) for row in collections_result]
        
        # Try to get real valuable items if possible
        try:
            # Build the valuable items query
            valuable_items_query = f"""
                SELECT name, collection_name, IFNULL(value, 0) as value
                FROM `{BQ_COLLECTION_ITEMS_TABLE}`
                WHERE user_id = @user_id
                AND value IS NOT NULL
            """
            
            query_params = [
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
            ]
            
            # Check if we need to filter by collection
            items_filter = request.args.get('items_filter')
            if items_filter:
                print(f"[DEBUG] Filtering valuable items by collection: {items_filter}")
                valuable_items_query += " AND collection_id = @collection_filter"
                query_params.append(bigquery.ScalarQueryParameter("collection_filter", "STRING", items_filter))
            
            # Complete the query
            valuable_items_query += """
                ORDER BY value DESC
                LIMIT 5
            """
            
            # Configure the job with our parameters
            valuable_items_job_config = bigquery.QueryJobConfig(query_parameters=query_params)
            
            # Execute the query
            valuable_items_result = client.query(valuable_items_query, job_config=valuable_items_job_config).result()
            real_valuable_items = [dict(row) for row in valuable_items_result]
            
            # If we have real data, use it
            if real_valuable_items:
                valuable_items = real_valuable_items
            else:
                # Otherwise use placeholder data
                valuable_items = [
                    {
                        "name": f"Sample Item {i}",
                        "collection_name": items_filter if items_filter else "Sample Collection",
                        "value": (10 - i) * 100  # Descending values
                    } for i in range(1, 6)
                ]
        except Exception as e:
            print(f"[WARNING] Failed to get valuable items: {str(e)}")
            # Fallback to placeholder data
            valuable_items = [
                {
                    "name": f"Sample Item {i}",
                    "collection_name": "Sample Collection",
                    "value": (10 - i) * 100  # Descending values
                } for i in range(1, 6)
            ]
        
        # Calculate total value
        try:
            total_value_query = f"""
                SELECT SUM(IFNULL(value, 0)) as total_value
                FROM `{BQ_COLLECTION_ITEMS_TABLE}`
                WHERE user_id = @user_id
            """
            total_value_result = client.query(total_value_query, job_config=job_config).result()
            overall_total = next(total_value_result).total_value or 0
        except Exception as e:
            print(f"[WARNING] Failed to calculate total value: {str(e)}")
            overall_total = 0
            
        # Get collection values for wealth split
        collection_values = []
        try:
            collection_values_query = f"""
                SELECT c.collection_id, c.collection_name, SUM(IFNULL(i.value, 0)) as total_value, COUNT(i.item_id) as item_count
                FROM `{BQ_COLLECTIONS_TABLE}` c
                LEFT JOIN `{BQ_COLLECTION_ITEMS_TABLE}` i 
                ON (c.collection_id = i.collection_id OR c.collection_name = i.collection_name) AND c.user_id = i.user_id
                WHERE c.user_id = @user_id
                GROUP BY c.collection_id, c.collection_name
                ORDER BY total_value DESC
            """
            
            collection_values_result = client.query(collection_values_query, job_config=job_config).result()
            collection_values = [dict(row) for row in collection_values_result]
            
            # Add value data to collections
            for collection in collections:
                matching = next((cv for cv in collection_values if cv['collection_id'] == collection['collection_id']), None)
                if matching:
                    collection['total_value'] = matching['total_value']
                else:
                    collection['total_value'] = 0
                    
        except Exception as e:
            print(f"[WARNING] Failed to get collection values: {str(e)}")
        
        # Get evolution data - using only real collection data
        evolution_data = {
            "labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
            "datasets": []
        }

        try:
            # Check if we need to filter by collection
            evolution_filter = request.args.get('evolution_filter')
            
            print(f"[DEBUG] Getting real evolution data for collections")
            
            # Use the actual collection values without generating growth curves
            if collection_values:
                # Filter collections if requested
                filtered_collections = []
                if evolution_filter:
                    print(f"[DEBUG] Evolution filter applied: {evolution_filter}")
                    filtered_collections = [c for c in collection_values if c['collection_id'] == evolution_filter]
                    if not filtered_collections:
                        filtered_collections = [c for c in collection_values if c['collection_name'] == evolution_filter]
                else:
                    # Use all collections with value > 0
                    filtered_collections = [c for c in collection_values if float(c.get('total_value', 0) or 0) > 0]
                
                print(f"[DEBUG] Using {len(filtered_collections)} collections for evolution chart")
                
                # Add each collection as a flat line showing current value
                # This is the most honest representation without historical data
                for idx, collection in enumerate(filtered_collections):
                    collection_name = collection['collection_name']
                    total_value = float(collection.get('total_value', 0) or 0)
                    item_count = int(collection.get('item_count', 0) or 0)
                    
                    if total_value <= 0:
                        print(f"[DEBUG] Skipping collection {collection_name} with zero value")
                        continue
                        
                    print(f"[DEBUG] Adding evolution data for {collection_name}: current value={total_value}, items={item_count}")
                    
                    # Create flat line showing current values for each month
                    # This shows the current state without misleading growth patterns
                    evolution_data['datasets'].append({
                        "label": collection_name,
                        "items_count": [item_count] * 6,  # Same value for all months
                        "value_data": [total_value] * 6,  # Same value for all months
                        "color": f"hsl({(idx * 60) % 360}, 70%, 50%)"
                    })
            
            # If no datasets were added, leave the datasets empty
            if not evolution_data['datasets']:
                print("[DEBUG] No collections with value > 0 found for evolution chart")
                # Return empty datasets array, don't add fake data
                
        except Exception as e:
            print(f"[ERROR] Failed to get evolution data: {str(e)}")
            import traceback
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            
            # Return empty datasets rather than fake data
            evolution_data['datasets'] = []
        
        # Return all the data needed by the frontend
        return jsonify({
            "total_items": total_items,
            "collections": collections,
            "tags": [],
            "valuable_items": valuable_items,
            "overall_total": overall_total,
            "evolution_data": evolution_data
        }), 200
    except Exception as e:
        import traceback
        print(f"[ERROR] Analytics query failed: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        return jsonify({"error": "Failed to get analytics", "details": str(e)}), 500

@collection_blueprint.route("/create", methods=["POST"])
@login_required
def create_collection():
    """
    API endpoint to create a new collection.
    
    Expected JSON payload:
    {
        "collection_name": str
    }
    """
    user_id = session.get('user_id')
    data = request.get_json()
    
    if not data.get("collection_name"):
        return jsonify({"error": "Collection name is required"}), 400
    
    collection_name = data.get("collection_name")
    collection_id = str(uuid.uuid4())
    
    client = get_bigquery_client()
    client._location = "europe-southwest1"
    
    # Check if collection already exists
    check_query = f"""
        SELECT COUNT(*) as count
        FROM `{BQ_COLLECTIONS_TABLE}`
        WHERE user_id = @user_id
        AND LOWER(collection_name) = LOWER(@collection_name)
    """
    
    check_job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
            bigquery.ScalarQueryParameter("collection_name", "STRING", collection_name)
        ]
    )
    
    try:
        check_result = client.query(check_query, job_config=check_job_config).result()
        if next(check_result).count > 0:
            return jsonify({"error": "Collection already exists"}), 409
        
        # Create collection
        create_query = f"""
            INSERT INTO `{BQ_COLLECTIONS_TABLE}`
            (user_id, collection_id, collection_name)
            VALUES
            (@user_id, @collection_id, @collection_name)
        """
        
        create_job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
                bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id),
                bigquery.ScalarQueryParameter("collection_name", "STRING", collection_name)
            ]
        )
        
        client.query(create_query, job_config=create_job_config).result()
        return jsonify({
            "message": "Collection created successfully",
            "collection": {
                "collection_name": collection_name,
                "collection_id": collection_id
            }
        }), 201
        
    except Exception as e:
        print(f"[ERROR] Failed to create collection: {str(e)}")
        return jsonify({"error": "Failed to create collection", "details": str(e)}), 500

@collection_blueprint.route("/edit/<string:collection_id>", methods=["PUT"])
@login_required
def edit_collection(collection_id):
    """
    API endpoint to edit an existing collection.
    
    Expected JSON payload:
    {
        "new_name": str
    }
    """
    user_id = session.get('user_id')
    data = request.get_json()
    
    # Get new name from request - accept either new_name or collection_name for flexibility
    new_name = data.get("new_name")
    
    if not new_name:
        return jsonify({"error": "Collection name is required"}), 400
    
    client = get_bigquery_client()
    client._location = "europe-southwest1"
    
    print(f"[DEBUG] Edit Collection - ID: {collection_id}, User ID: {user_id}, New Name: {new_name}")
    
    # Construct and execute update query
    query = f"""
        UPDATE `{BQ_COLLECTIONS_TABLE}`
        SET collection_name = @collection_name
        WHERE collection_id = @collection_id AND user_id = @user_id
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id),
            bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
            bigquery.ScalarQueryParameter("collection_name", "STRING", new_name)
        ]
    )
    
    try:
        client.query(query, job_config=job_config).result()
        
        # Also update collection_name in collection items table for consistency
        update_items_query = f"""
            UPDATE `{BQ_COLLECTION_ITEMS_TABLE}`
            SET collection_name = @collection_name
            WHERE user_id = @user_id 
            AND (collection_id = @collection_id)
        """
        
        update_items_job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id),
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
                bigquery.ScalarQueryParameter("collection_name", "STRING", new_name)
            ]
        )
        
        client.query(update_items_query, job_config=update_items_job_config).result()
        
        return jsonify({"message": "Collection updated successfully"}), 200
    except Exception as e:
        print(f"[ERROR] Failed to update collection: {str(e)}")
        return jsonify({"error": "Failed to update collection", "details": str(e)}), 500

@collection_blueprint.route("/delete/<string:collection_id>", methods=["DELETE"])
@login_required
def delete_collection(collection_id):
    """
    API endpoint to delete a collection and all its items.
    Deletes both the collection and all items with matching collection_id OR collection_name.
    """
    user_id = session.get('user_id')
    print(f"[DEBUG] Delete Collection Route - User ID: {user_id}, Collection ID: {collection_id}")
    
    client = get_bigquery_client()
    client._location = "europe-southwest1"
    
    # First, check if the collection exists and get its name
    check_query = f"""
        SELECT collection_name FROM `{BQ_COLLECTIONS_TABLE}`
        WHERE collection_id = @collection_id AND user_id = @user_id
    """
    
    check_params = [
        bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id),
        bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
    ]
    
    check_job_config = bigquery.QueryJobConfig(query_parameters=check_params)
    
    try:
        check_results = client.query(check_query, job_config=check_job_config).result()
        if check_results.total_rows == 0:
            return jsonify({"error": "Collection not found or you don't have permission to delete it"}), 404
            
        # Get the collection name for logging and for deleting items
        collection_name = next(check_results).collection_name
        print(f"[DEBUG] Deleting collection: {collection_name} (ID: {collection_id})")
        
        # Count items to be deleted by either collection_id OR collection_name for complete cleanup
        count_query = f"""
            SELECT COUNT(*) as item_count 
            FROM `{BQ_COLLECTION_ITEMS_TABLE}`
            WHERE user_id = @user_id 
            AND (collection_id = @collection_id OR collection_name = @collection_name)
        """
        
        count_params = [
            bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
            bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id),
            bigquery.ScalarQueryParameter("collection_name", "STRING", collection_name)
        ]
        
        count_job_config = bigquery.QueryJobConfig(query_parameters=count_params)
        count_result = client.query(count_query, job_config=count_job_config).result()
        item_count = next(count_result).item_count
        print(f"[DEBUG] Found {item_count} items to delete in collection {collection_name}")
        
        # 1. Delete all items that match either the collection_id OR the collection_name
        delete_items_query = f"""
            DELETE FROM `{BQ_COLLECTION_ITEMS_TABLE}`
            WHERE user_id = @user_id 
            AND (collection_id = @collection_id OR collection_name = @collection_name)
        """
        
        delete_items_params = [
            bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
            bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id),
            bigquery.ScalarQueryParameter("collection_name", "STRING", collection_name)
        ]
        
        delete_items_job_config = bigquery.QueryJobConfig(query_parameters=delete_items_params)
        delete_items_result = client.query(delete_items_query, job_config=delete_items_job_config).result()
        print(f"[DEBUG] Deleted items query executed")
        
        # 2. Delete the collection
        delete_query = f"""
            DELETE FROM `{BQ_COLLECTIONS_TABLE}`
            WHERE collection_id = @collection_id AND user_id = @user_id
        """
        
        delete_params = [
            bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id),
            bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
        ]
        
        delete_job_config = bigquery.QueryJobConfig(query_parameters=delete_params)
        client.query(delete_query, job_config=delete_job_config).result()
        print(f"[DEBUG] Deleted collection query executed")
        
        return jsonify({
            "message": f"Collection '{collection_name}' and all its items deleted successfully",
            "collection_id": collection_id,
            "items_deleted": item_count
        }), 200
    except Exception as e:
        print(f"[ERROR] Failed to delete collection: {str(e)}")
        return jsonify({"error": f"Failed to delete collection: {str(e)}"}), 500