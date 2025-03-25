# Collection Manager

A full-stack web application for managing and tracking collections of collectible items with detailed analytics and visualization.

## Overview

Collection Manager helps collectors organize, track, and analyze their collectibles in one place. It provides a user-friendly interface to manage collections, add items with details like acquisition date and value, search across collections, and visualize collection data through interactive charts.

## Features

- **User Authentication**: Secure login and registration system
- **Collection Management**: Create, edit, and delete collections
- **Item Management**: Add, edit, delete, and categorize items in collections
- **Search & Filter**: Find items across collections with advanced filtering options
- **Analytics Dashboard**:
  - Total value of collections
  - Most valuable items
  - Collection growth over time
  - Wealth distribution across collections
- **Responsive Design**: Optimized for desktop and mobile devices

## Technology Stack

### Backend

- **Python 3.10** with Flask web framework
- **Google BigQuery** for data storage
- **Flask-JWT-Extended** for authentication
- **Flask-Session** for server-side session management

### Frontend

- **HTML5/CSS3/JavaScript**
- **Chart.js** for data visualization
- **Responsive design** for multi-device support

### Deployment

- **Google Cloud Platform** (App Engine)
- **Cloud Build** for CI/CD pipeline

## Project Structure

```
├── backend/               # Backend Flask application
│   ├── app/               # Application modules
│   │   ├── config/        # Configuration files
│   │   ├── models/        # Data models
│   │   ├── routes/        # API route handlers
│   │   │   ├── auth.py    # Authentication endpoints
│   │   │   ├── collection.py # Collection management endpoints
│   │   └── utils/         # Utility functions
│   ├── app.py             # Main application setup
│   └── wsgi.py            # WSGI entry point
├── capstone_frontend_karim/ # Frontend files
│   ├── static/            # Static assets (JS, CSS, images)
│   └── templates/         # HTML templates
├── data/                  # Data files and samples
├── app.yaml               # App Engine configuration
├── main.py                # Entry point for App Engine
├── requirements.txt       # Python dependencies
└── cloudbuild.yaml        # Cloud Build configuration
```

## Installation

### Prerequisites

- Python 3.10+
- Google Cloud SDK
- Google BigQuery account with appropriate permissions

### Local Development Setup

1. Clone the repository:

   ```
   git clone https://github.com/yourusername/collection-manager.git
   cd collection-manager
   ```

2. Create and activate a virtual environment:

   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:

   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables:

   ```
   export FLASK_ENV=development
   export SECRET_KEY=your_secret_key
   ```

5. Run the application:

   ```
   python main.py
   ```

6. Access the application at http://localhost:8080

## Deployment

The application is configured for deployment to Google App Engine:

1. Make sure you have the Google Cloud SDK installed and configured

2. Deploy using gcloud:
   ```
   gcloud app deploy
   ```

## API Endpoints

The application provides the following API endpoints:

### Authentication

- `POST /api/auth/register`: Register a new user
- `POST /api/auth/login`: Log in and receive a session
- `POST /api/auth/logout`: Log out and invalidate session

### Collections

- `GET /api/collection/`: Get all collection items
- `GET /api/collection/collections`: Get all collections
- `POST /api/collection/create`: Create a new collection
- `PUT /api/collection/edit/<collection_id>`: Update a collection
- `DELETE /api/collection/delete/<collection_id>`: Delete a collection

### Items

- `POST /api/collection/add`: Add a new item
- `PUT /api/collection/item/update/<item_id>`: Update an item
- `DELETE /api/collection/item/delete/<item_id>`: Delete an item
- `GET /api/collection/search`: Search for items
- `GET /api/collection/analytics`: Get collection analytics

## Future Enhancements

- User profile customization
- Image upload for collectible items
- Social sharing functionality
- Mobile app version
- Export/import functionality

## Contact

For questions or support, please contact karimelachkar@student.ie.edu.
