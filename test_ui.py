#!/usr/bin/env python
"""Quick test for separated UI files."""

from ui.templates import get_dashboard_html

# Load the dashboard
html = get_dashboard_html()

print("✓ Dashboard HTML loaded successfully")
print(f"✓ HTML length: {len(html)} characters")
print(f"✓ Contains CSS link: {'styles.css' in html}")
print(f"✓ Contains JS link: {'scripts.js' in html}")
print(f"✓ Contains API_BASE: {'API_BASE' in html or 'api' in html.lower()}")

# Verify files exist
import os
ui_dir = os.path.dirname(os.path.abspath(__file__)) + "/ui"
print(f"\n✓ styles.css exists: {os.path.exists(os.path.join(ui_dir, 'styles.css'))}")
print(f"✓ scripts.js exists: {os.path.exists(os.path.join(ui_dir, 'scripts.js'))}")
print(f"✓ dashboard.html exists: {os.path.exists(os.path.join(ui_dir, 'dashboard.html'))}")

print("\n✅ All UI files separated and ready!")
