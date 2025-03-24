from google.cloud import bigquery
import os

# Set up BigQuery Client
def get_bigquery_client():
    return bigquery.Client(project="capstone-integration-karim", location="europe-southwest1")

# Define dataset and table names
BQ_DATASET = "my_collections_dataset"
BQ_USERS_TABLE = f"{BQ_DATASET}.users"
BQ_COLLECTION_ITEMS_TABLE = f"{BQ_DATASET}.collection_items"
BQ_COLLECTIONS_TABLE = f"{BQ_DATASET}.collections"