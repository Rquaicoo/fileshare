"""
UI Configuration and Constants
"""

import os

# Directories
SHARED_DIR = "shared"
DOWNLOADS_DIR = "downloads"
DISCOVERY_URL = "http://localhost:8000"

# Server
UI_HOST = "0.0.0.0"
UI_PORT = 8080

# Ensure directories exist
os.makedirs(SHARED_DIR, exist_ok=True)
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
