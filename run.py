#!/usr/bin/env python3
"""
Quick launcher for the complete P2P File Sharing System with Modern UI.
Starts:
  1. Discovery Service (port 8000)
  2. Peer Server (port 9000)
  3. Web UI Dashboard (port 8080)

All in one command!
"""

import subprocess
import time
import sys
import os
from threading import Thread


def print_banner():
    """Print fancy startup banner."""
    banner = """
    ╔════════════════════════════════════════════════════════════╗
    ║          P2P FILE SHARING SYSTEM - UI LAUNCHER             ║
    ║         Modern Web Dashboard & Secure Peer Network         ║
    ╚════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_instruction(title, instruction):
    """Pretty print an instruction."""
    print(f"  📝 {title}")
    print(f"     {instruction}")
    print()


def start_service(name, command, port):
    """Start a service and monitor it."""
    print(f"  [✓] Starting {name} on port {port}...")
    try:
        subprocess.Popen(command, shell=True, cwd=os.getcwd())
    except Exception as e:
        print(f"  [✗] Failed to start {name}: {e}")
        return False
    return True


def main():
    print_banner()

    print("=" * 62)
    print("STARTING SERVICES...")
    print("=" * 62)
    print()

    # Start discovery service
    print("1️⃣  DISCOVERY SERVICE")
    start_service(
        "Discovery Service",
        'python -m uvicorn peer.main:app --host 0.0.0.0 --port 8000 --log-level error',
        8000
    )
    time.sleep(1)
    print()

    # Start peer server
    print("2️⃣  PEER SERVER")
    start_service(
        "Peer Server",
        'python peer/runner.py --mode peer --peer-port 9000 --shared-dir shared',
        9000
    )
    time.sleep(1)
    print()

    # Start web UI
    print("3️⃣  WEB UI DASHBOARD")
    start_service(
        "Web UI",
        'python -m uvicorn ui.api:app --host 0.0.0.0 --port 8080 --log-level error',
        8080
    )
    time.sleep(2)
    print()

    # Print success message
    print("=" * 62)
    print("✓ ALL SERVICES STARTED!")
    print("=" * 62)
    print()

    print("📊 DASHBOARD ACCESS")
    print_instruction("Web UI", "→ http://localhost:8080")
    print_instruction("Discovery API", "→ http://localhost:8000")
    print_instruction("Peer Server", "→ 127.0.0.1:9000")

    print("📁 DIRECTORIES")
    print_instruction("Shared Files", "→ ./shared/")
    print_instruction("Downloaded Files", "→ ./downloads/")
    print_instruction("Keys", "→ ./keys/")

    print("🎯 NEXT STEPS")
    print_instruction("1. Open browser", "http://localhost:8080")
    print_instruction("2. Upload files", "Use the 'Share Files' section")
    print_instruction("3. Browse peers", "View 'Online Peers'")
    print_instruction("4. Download files", "Search and download from peers")

    print("🔐 FEATURES")
    print_instruction("RSA-2048 + AES-256", "Bank-grade encryption")
    print_instruction("Concurrent Downloads", "4 chunks in parallel")
    print_instruction("Auto-Discovery", "Peers auto-register")
    print_instruction("File Verification", "SHA-256 integrity checks")

    print("🛑 TO STOP")
    print_instruction("Press Ctrl+C", "Closes all services")
    print()

    print("=" * 62)
    print("SERVICES RUNNING - DASHBOARD READY AT http://localhost:8080")
    print("=" * 62)
    print()

    # Keep the script running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down services...")
        sys.exit(0)


if __name__ == "__main__":
    main()
