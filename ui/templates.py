"""
HTML template for the P2P file sharing dashboard UI.

This module manages the dashboard HTML by reading separate CSS and JavaScript files.
The actual template is loaded from dashboard.html in the same directory.
"""

import os
from pathlib import Path


def get_dashboard_html():
    """Read and return the dashboard HTML with CSS and JavaScript assets."""
    template_dir = Path(__file__).parent
    
    try:
        # Read the base HTML template
        html_path = template_dir / 'dashboard.html'
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        return html_content
    except Exception as e:
        # Fallback if files can't be read
        print(f"Error loading dashboard template: {e}")
        return get_fallback_html()


def get_fallback_html():
    """Fallback HTML in case file loading fails."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>P2P File Sharing - Dashboard</title>
</head>
<body>
    <p>Dashboard loading error. Please check server logs.</p>
</body>
</html>
"""
