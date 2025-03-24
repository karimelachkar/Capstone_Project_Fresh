"""
Collection management routes for the Collection Manager application.
Handles CRUD operations for collections and collection items, including search and analytics.
"""

import uuid
from flask import Blueprint, request, jsonify, session, Response
from functools import wraps
from backend.app.config.bigquery import get_bigquery_client, BQ_COLLECTION_ITEMS_TABLE, BQ_COLLECTIONS_TABLE
from google.cloud import bigquery
import csv
import io
from datetime import datetime

# Initialize Blueprint for collection routes
collection_blueprint = Blueprint("collection", __name__)

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
        SELECT collection_name 
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
        collections = [{"collection_name": row["collection_name"]} for row in results]
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
                AND NOT STARTS_WITH(name, 'Collection: ')  -- Exclude placeholder items
                GROUP BY collection_name
                HAVING COUNT(*) > 0  -- Only include collections with at least one actual item
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
                "collection_name": str
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
        
        if not item_id or not collection_name:
            error_count += 1
            errors.append(f"Missing item_id or collection_name for assignment: {assignment}")
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
                
            # Update the collection name
            update_query = f"""
                UPDATE `{BQ_COLLECTION_ITEMS_TABLE}`
                SET collection_name = @collection_name
                WHERE item_id = @item_id AND user_id = @user_id
            """
            
            update_job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("collection_name", "STRING", collection_name),
                    bigquery.ScalarQueryParameter("item_id", "STRING", item_id),
                    bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
                ]
            )
            
            client.query(update_query, job_config=update_job_config).result()
            success_count += 1
            print(f"[DEBUG] Assign Collections Route - Successfully assigned item {item_id} to collection {collection_name}")
            
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
    API endpoint to add a new item to the collection.
    
    Expected JSON payload:
    {
        "name": str,
        "description": str,
        "collection_name": str,
        "image_url": str (optional),
        "tags": list (optional)
    }
    """
    user_id = session.get('user_id')
    data = request.get_json()
    
    # Validate required fields
    if not data.get("name"):
        return jsonify({"error": "Name is required"}), 400
        
    # Generate unique item_id
    item_id = str(uuid.uuid4())
    
    # Prepare item data
    item_data = {
        "item_id": item_id,
        "user_id": user_id,
        "name": data.get("name"),
        "description": data.get("description", ""),
        "collection_name": data.get("collection_name", ""),
        "image_url": data.get("image_url", ""),
        "tags": data.get("tags", []),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    
    # Insert item into BigQuery
    client = get_bigquery_client()
    client._location = "europe-southwest1"
    
    query = f"""
        INSERT INTO `{BQ_COLLECTION_ITEMS_TABLE}` 
        (item_id, user_id, name, description, collection_name, image_url, tags, created_at, updated_at)
        VALUES 
        (@item_id, @user_id, @name, @description, @collection_name, @image_url, @tags, @created_at, @updated_at)
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("item_id", "STRING", item_data["item_id"]),
            bigquery.ScalarQueryParameter("user_id", "STRING", item_data["user_id"]),
            bigquery.ScalarQueryParameter("name", "STRING", item_data["name"]),
            bigquery.ScalarQueryParameter("description", "STRING", item_data["description"]),
            bigquery.ScalarQueryParameter("collection_name", "STRING", item_data["collection_name"]),
            bigquery.ScalarQueryParameter("image_url", "STRING", item_data["image_url"]),
            bigquery.ArrayQueryParameter("tags", "STRING", item_data["tags"]),
            bigquery.ScalarQueryParameter("created_at", "STRING", item_data["created_at"]),
            bigquery.ScalarQueryParameter("updated_at", "STRING", item_data["updated_at"])
        ]
    )
    
    try:
        client.query(query, job_config=job_config).result()
        return jsonify({"message": "Item added successfully", "item": item_data}), 201
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
        "image_url": str (optional),
        "tags": list (optional)
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
        bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
        bigquery.ScalarQueryParameter("updated_at", "STRING", datetime.utcnow().isoformat())
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
    
    if "image_url" in data:
        update_fields.append("image_url = @image_url")
        query_params.append(bigquery.ScalarQueryParameter("image_url", "STRING", data["image_url"]))
    
    if "tags" in data:
        update_fields.append("tags = @tags")
        query_params.append(bigquery.ArrayQueryParameter("tags", "STRING", data["tags"]))
    
    if not update_fields:
        return jsonify({"error": "No valid fields to update"}), 400
    
    # Construct and execute update query
    client = get_bigquery_client()
    client._location = "europe-southwest1"
    
    query = f"""
        UPDATE `{BQ_COLLECTION_ITEMS_TABLE}`
        SET {', '.join(update_fields)}, updated_at = @updated_at
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
def search_collection():
    """
    API endpoint to search items in the collection.
    Supports searching by name, description, tags, and collection name.
    
    Query Parameters:
        q (str): Search query
        collection (str, optional): Filter by collection name
        tags (str, optional): Comma-separated list of tags to filter by
    """
    user_id = session.get('user_id')
    query = request.args.get('q', '')
    collection = request.args.get('collection', '')
    tags = request.args.get('tags', '').split(',') if request.args.get('tags') else []
    
    if not query:
        return jsonify({"error": "Search query is required"}), 400
    
    client = get_bigquery_client()
    client._location = "europe-southwest1"
    
    # Build search query
    search_query = f"""
        SELECT * FROM `{BQ_COLLECTION_ITEMS_TABLE}`
        WHERE user_id = @user_id
        AND (
            LOWER(name) LIKE LOWER(@query)
            OR LOWER(description) LIKE LOWER(@query)
            OR LOWER(collection_name) LIKE LOWER(@query)
        )
    """
    
    query_params = [
        bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
        bigquery.ScalarQueryParameter("query", "STRING", f"%{query}%")
    ]
    
    # Add collection filter if specified
    if collection:
        search_query += " AND LOWER(collection_name) = LOWER(@collection)"
        query_params.append(bigquery.ScalarQueryParameter("collection", "STRING", collection))
    
    # Add tags filter if specified
    if tags:
        search_query += " AND EXISTS (SELECT 1 FROM UNNEST(tags) tag WHERE tag IN UNNEST(@tags))"
        query_params.append(bigquery.ArrayQueryParameter("tags", "STRING", tags))
    
    job_config = bigquery.QueryJobConfig(query_parameters=query_params)
    
    try:
        results = client.query(search_query, job_config=job_config).result()
        items = [dict(row) for row in results]
        return jsonify({"items": items}), 200
    except Exception as e:
        print(f"[ERROR] Search failed: {str(e)}")
        return jsonify({"error": "Search failed", "details": str(e)}), 500

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
    
    # Get total items count
    items_query = f"""
        SELECT COUNT(*) as total_items
        FROM `{BQ_COLLECTION_ITEMS_TABLE}`
        WHERE user_id = @user_id
    """
    
    # Get items by collection
    collections_query = f"""
        SELECT collection_name, COUNT(*) as item_count
        FROM `{BQ_COLLECTION_ITEMS_TABLE}`
        WHERE user_id = @user_id
        AND collection_name IS NOT NULL
        AND TRIM(collection_name) != ''
        GROUP BY collection_name
        ORDER BY item_count DESC
    """
    
    # Get tag statistics
    tags_query = f"""
        SELECT tag, COUNT(*) as usage_count
        FROM `{BQ_COLLECTION_ITEMS_TABLE}`,
        UNNEST(tags) as tag
        WHERE user_id = @user_id
        GROUP BY tag
        ORDER BY usage_count DESC
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
        tags_result = client.query(tags_query, job_config=job_config).result()
        
        # Process results
        total_items = next(items_result).total_items
        collections = [dict(row) for row in collections_result]
        tags = [dict(row) for row in tags_result]
        
        return jsonify({
            "total_items": total_items,
            "collections": collections,
            "tags": tags
        }), 200
    except Exception as e:
        print(f"[ERROR] Analytics query failed: {str(e)}")
        return jsonify({"error": "Failed to get analytics", "details": str(e)}), 500

@collection_blueprint.route("/create", methods=["POST"])
@login_required
def create_collection():
    """
    API endpoint to create a new collection.
    
    Expected JSON payload:
    {
        "collection_name": str,
        "description": str (optional)
    }
    """
    user_id = session.get('user_id')
    data = request.get_json()
    
    if not data.get("collection_name"):
        return jsonify({"error": "Collection name is required"}), 400
    
    collection_name = data.get("collection_name")
    description = data.get("description", "")
    
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
            (user_id, collection_name, description, created_at, updated_at)
            VALUES
            (@user_id, @collection_name, @description, @created_at, @updated_at)
        """
        
        create_job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
                bigquery.ScalarQueryParameter("collection_name", "STRING", collection_name),
                bigquery.ScalarQueryParameter("description", "STRING", description),
                bigquery.ScalarQueryParameter("created_at", "STRING", datetime.utcnow().isoformat()),
                bigquery.ScalarQueryParameter("updated_at", "STRING", datetime.utcnow().isoformat())
            ]
        )
        
        client.query(create_query, job_config=create_job_config).result()
        return jsonify({
            "message": "Collection created successfully",
            "collection": {
                "collection_name": collection_name,
                "description": description
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
        "collection_name": str (optional),
        "description": str (optional)
    }
    """
    user_id = session.get('user_id')
    data = request.get_json()
    
    if not any(data.values()):
        return jsonify({"error": "No fields to update"}), 400
    
    client = get_bigquery_client()
    client._location = "europe-southwest1"
    
    # Build update query dynamically
    update_fields = []
    query_params = [
        bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id),
        bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
        bigquery.ScalarQueryParameter("updated_at", "STRING", datetime.utcnow().isoformat())
    ]
    
    if "collection_name" in data:
        update_fields.append("collection_name = @collection_name")
        query_params.append(bigquery.ScalarQueryParameter("collection_name", "STRING", data["collection_name"]))
    
    if "description" in data:
        update_fields.append("description = @description")
        query_params.append(bigquery.ScalarQueryParameter("description", "STRING", data["description"]))
    
    if not update_fields:
        return jsonify({"error": "No valid fields to update"}), 400
    
    # Construct and execute update query
    query = f"""
        UPDATE `{BQ_COLLECTIONS_TABLE}`
        SET {', '.join(update_fields)}, updated_at = @updated_at
        WHERE collection_id = @collection_id AND user_id = @user_id
    """
    
    job_config = bigquery.QueryJobConfig(query_parameters=query_params)
    
    try:
        client.query(query, job_config=job_config).result()
        return jsonify({"message": "Collection updated successfully"}), 200
    except Exception as e:
        print(f"[ERROR] Failed to update collection: {str(e)}")
        return jsonify({"error": "Failed to update collection", "details": str(e)}), 500

@collection_blueprint.route("/delete", methods=["POST"])
@login_required
def delete_collection_post():
    """
    API endpoint to delete a collection and all its items.
    
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
    
    client = get_bigquery_client()
    client._location = "europe-southwest1"
    
    try:
        # First delete all items in the collection
        delete_items_query = f"""
            DELETE FROM `{BQ_COLLECTION_ITEMS_TABLE}`
            WHERE user_id = @user_id
            AND collection_name = @collection_name
        """
        
        delete_items_job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
                bigquery.ScalarQueryParameter("collection_name", "STRING", collection_name)
            ]
        )
        
        client.query(delete_items_query, job_config=delete_items_job_config).result()
        
        # Then delete the collection itself
        delete_collection_query = f"""
            DELETE FROM `{BQ_COLLECTIONS_TABLE}`
            WHERE user_id = @user_id
            AND collection_name = @collection_name
        """
        
        delete_collection_job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
                bigquery.ScalarQueryParameter("collection_name", "STRING", collection_name)
            ]
        )
        
        client.query(delete_collection_query, job_config=delete_collection_job_config).result()
        
        return jsonify({"message": "Collection and its items deleted successfully"}), 200
    except Exception as e:
        print(f"[ERROR] Failed to delete collection: {str(e)}")
        return jsonify({"error": "Failed to delete collection", "details": str(e)}), 500

@collection_blueprint.route("/delete/<string:collection_id>", methods=["DELETE"])
@login_required
def delete_collection(collection_id):
    """
    API endpoint to delete a collection by its ID.
    
    Args:
        collection_id (str): The ID of the collection to delete
    """
    user_id = session.get('user_id')
    
    client = get_bigquery_client()
    client._location = "europe-southwest1"
    
    try:
        # First get the collection name
        get_name_query = f"""
            SELECT collection_name
            FROM `{BQ_COLLECTIONS_TABLE}`
            WHERE collection_id = @collection_id
            AND user_id = @user_id
        """
        
        get_name_job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id),
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
            ]
        )
        
        name_result = client.query(get_name_query, job_config=get_name_job_config).result()
        collection = next(name_result, None)
        
        if not collection:
            return jsonify({"error": "Collection not found"}), 404
        
        collection_name = collection.collection_name
        
        # Delete all items in the collection
        delete_items_query = f"""
            DELETE FROM `{BQ_COLLECTION_ITEMS_TABLE}`
            WHERE user_id = @user_id
            AND collection_name = @collection_name
        """
        
        delete_items_job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
                bigquery.ScalarQueryParameter("collection_name", "STRING", collection_name)
            ]
        )
        
        client.query(delete_items_query, job_config=delete_items_job_config).result()
        
        # Delete the collection
        delete_collection_query = f"""
            DELETE FROM `{BQ_COLLECTIONS_TABLE}`
            WHERE collection_id = @collection_id
            AND user_id = @user_id
        """
        
        delete_collection_job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id),
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
            ]
        )
        
        client.query(delete_collection_query, job_config=delete_collection_job_config).result()
        
        return jsonify({"message": "Collection and its items deleted successfully"}), 200
    except Exception as e:
        print(f"[ERROR] Failed to delete collection: {str(e)}")
        return jsonify({"error": "Failed to delete collection", "details": str(e)}), 500

@collection_blueprint.route("/debug", methods=["GET"])
@login_required
def debug_data():
    """
    Debug endpoint to get detailed information about the user's data.
    Only accessible to admin users.
    """
    # Only allow specific admin users
    admin_users = ["admin@example.com"]  # Replace with actual admin users
    user_id = session.get('user_id')
    
    if user_id not in admin_users:
        return jsonify({"error": "Unauthorized access"}), 403
    
    client = get_bigquery_client()
    client._location = "europe-southwest1"
    
    try:
        # Get all user data
        query = f"""
            SELECT * FROM `{BQ_COLLECTION_ITEMS_TABLE}`
            WHERE user_id = @user_id
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
            ]
        )
        
        results = client.query(query, job_config=job_config).result()
        items = [dict(row) for row in results]
        
        return jsonify({
            "user_id": user_id,
            "items": items
        }), 200
    except Exception as e:
        print(f"[ERROR] Debug data query failed: {str(e)}")
        return jsonify({"error": "Failed to get debug data", "details": str(e)}), 500

@collection_blueprint.route("/collections-list", methods=["GET"])
@login_required
def get_collections_list():
    """
    API endpoint to get a detailed list of all collections with their items.
    Returns collections with item counts and basic statistics.
    """
    user_id = session.get('user_id')
    
    client = get_bigquery_client()
    client._location = "europe-southwest1"
    
    query = f"""
        SELECT 
            c.collection_name,
            c.description,
            COUNT(i.item_id) as item_count,
            MIN(i.created_at) as oldest_item,
            MAX(i.updated_at) as newest_item
        FROM `{BQ_COLLECTIONS_TABLE}` c
        LEFT JOIN `{BQ_COLLECTION_ITEMS_TABLE}` i
        ON c.user_id = i.user_id
        AND c.collection_name = i.collection_name
        WHERE c.user_id = @user_id
        GROUP BY c.collection_name, c.description
        ORDER BY item_count DESC
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
        ]
    )
    
    try:
        results = client.query(query, job_config=job_config).result()
        collections = [dict(row) for row in results]
        return jsonify({"collections": collections}), 200
    except Exception as e:
        print(f"[ERROR] Failed to get collections list: {str(e)}")
        return jsonify({"error": "Failed to get collections list", "details": str(e)}), 500

@collection_blueprint.route("/export/<string:collection_name>", methods=["GET"])
@login_required
def export_collection(collection_name):
    """
    API endpoint to export a collection's items to CSV format.
    
    Args:
        collection_name (str): The name of the collection to export
    """
    user_id = session.get('user_id')
    
    client = get_bigquery_client()
    client._location = "europe-southwest1"
    
    query = f"""
        SELECT 
            name,
            description,
            collection_name,
            image_url,
            tags,
            created_at,
            updated_at
        FROM `{BQ_COLLECTION_ITEMS_TABLE}`
        WHERE user_id = @user_id
        AND collection_name = @collection_name
        ORDER BY created_at DESC
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
            bigquery.ScalarQueryParameter("collection_name", "STRING", collection_name)
        ]
    )
    
    try:
        results = client.query(query, job_config=job_config).result()
        items = [dict(row) for row in results]
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "Name",
            "Description",
            "Collection",
            "Image URL",
            "Tags",
            "Created At",
            "Updated At"
        ])
        
        # Write data
        for item in items:
            writer.writerow([
                item["name"],
                item["description"],
                item["collection_name"],
                item["image_url"],
                ", ".join(item["tags"]),
                item["created_at"],
                item["updated_at"]
            ])
        
        # Create response
        response = Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={collection_name}_export.csv"
            }
        )
        
        return response
    except Exception as e:
        print(f"[ERROR] Failed to export collection: {str(e)}")
        return jsonify({"error": "Failed to export collection", "details": str(e)}), 500