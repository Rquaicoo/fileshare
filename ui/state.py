"""
Global UI State Management
"""

# Global state for UI
ui_state = {
    "peer_id": None,
    "public_key": None,
    "port": 9000,
    "shared_files": [],
    "registered": False,
    "download_progress": {},
    "online_peers": []
}


def get_state():
    """Get current UI state."""
    return ui_state


def update_state(key, value):
    """Update UI state."""
    ui_state[key] = value


def reset_state():
    """Reset UI state."""
    global ui_state
    ui_state = {
        "peer_id": None,
        "public_key": None,
        "port": 9000,
        "shared_files": [],
        "registered": False,
        "download_progress": {},
        "online_peers": []
    }
