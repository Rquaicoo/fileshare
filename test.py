"""
Test helper script for the P2P File Sharing system.
Creates sample files and provides testing utilities.
"""

import os
import sys
from pathlib import Path


def print_header(title):
    """Print a styled section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def print_step(step, description):
    """Print a numbered step."""
    print(f"\n  {step}. {description}")


def create_test_files(directory="shared"):
    """Create various test files for demonstration."""
    os.makedirs(directory, exist_ok=True)

    files = {
        "README.txt": "This is a test file for P2P File Sharing System.\n" * 50,
        "hello.txt": "Hello, World! This is a simple test file.\n",
        "data.json": '{"name": "P2P", "version": 1.0, "features": ["encryption", "chunks", "concurrent", "discovery"]}\n',
        "script.py": """#!/usr/bin/env python3
# Sample Python script
def greet(name):
    print(f"Hello, {name}!")
    
if __name__ == "__main__":
    greet("P2P File Sharing")
""",
        "document.txt": "Lorem ipsum dolor sit amet, consectetur adipiscing elit.\n" * 100,
    }

    created = []
    for filename, content in files.items():
        path = os.path.join(directory, filename)
        with open(path, 'w') as f:
            f.write(content)
        size = os.path.getsize(path)
        created.append((filename, size))
        print(f"    ✓ {filename} ({size} bytes)")

    return created


def create_large_file(filename="largefile.bin", size_mb=10, directory="shared"):
    """Create a large binary file for testing concurrent downloads."""
    os.makedirs(directory, exist_ok=True)
    
    filepath = os.path.join(directory, filename)
    size_bytes = size_mb * 1024 * 1024
    
    print(f"    Creating {filename} ({size_mb} MB)...", end='', flush=True)
    
    with open(filepath, 'wb') as f:
        # Write in chunks to avoid memory issues
        chunk_size = 1024 * 1024  # 1MB chunks
        for _ in range(0, size_bytes, chunk_size):
            chunk = os.urandom(min(chunk_size, size_bytes - f.tell()))
            f.write(chunk)
    
    actual_size = os.path.getsize(filepath)
    print(f" ✓ ({actual_size} bytes)")
    return actual_size


def setup_test_environment():
    """Complete setup for testing."""
    print_header("P2P FILE SHARING - TEST SETUP")
    
    print("\n📁 Creating directories...")
    for directory in ["shared", "downloads", "keys"]:
        os.makedirs(directory, exist_ok=True)
        print(f"    ✓ {directory}/")
    
    print("\n📝 Creating test files...")
    files = create_test_files()
    
    print(f"\n📦 Creating large file for testing...")
    large_size = create_large_file("testfile_10mb.bin", size_mb=10)
    
    print_header("SETUP COMPLETE")
    
    print("\n✓ Test environment ready!")
    print(f"  - {len(files)} test files created in shared/")
    print(f"  - 1 large file (10 MB) for testing concurrent downloads")
    print(f"  - Total: {sum(f[1] for f in files) + large_size} bytes")
    
    print("\n🚀 TO START TESTING:")
    print("  1. Run: python run.py")
    print("  2. Open: http://localhost:8080")
    print("  3. Upload files from shared/ directory")
    print("  4. Test concurrent downloads")
    print("  5. Verify file integrity")
    
    return True


def cleanup_downloads():
    """Clean up downloaded test files."""
    if os.path.exists("downloads"):
        files = os.listdir("downloads")
        for f in files:
            path = os.path.join("downloads", f)
            os.remove(path)
        print(f"✓ Deleted {len(files)} downloaded files")
    else:
        print("✓ No downloads directory to clean")


def check_environment():
    """Check if system is properly set up."""
    print_header("ENVIRONMENT CHECK")
    
    checks = {
        "shared/": os.path.isdir("shared"),
        "downloads/": os.path.isdir("downloads"),
        "keys/": os.path.isdir("keys"),
        "peer/main.py": os.path.isfile("peer/main.py"),
        "peer/server.py": os.path.isfile("peer/server.py"),
        "peer/client.py": os.path.isfile("peer/client.py"),
        "peer/ui_api.py": os.path.isfile("peer/ui_api.py"),
        "peer/runner.py": os.path.isfile("peer/runner.py"),
    }
    
    all_ok = True
    for item, exists in checks.items():
        status = "✓" if exists else "✗"
        print(f"  {status} {item}")
        if not exists:
            all_ok = False
    
    print()
    
    if all_ok:
        print("  ✓ All required files present")
        return True
    else:
        print("  ✗ Some files missing. Make sure you're in the Fileshare directory.")
        return False


def show_file_stats():
    """Show statistics about shared and downloaded files."""
    print_header("FILE STATISTICS")
    
    def count_files(directory):
        if not os.path.exists(directory):
            return 0, 0
        
        files = []
        total_size = 0
        for f in os.listdir(directory):
            path = os.path.join(directory, f)
            if os.path.isfile(path):
                size = os.path.getsize(path)
                files.append((f, size))
                total_size += size
        
        return len(files), total_size
    
    shared_count, shared_size = count_files("shared")
    download_count, download_size = count_files("downloads")
    
    print(f"\n📂 SHARED FILES")
    print(f"  Files: {shared_count}")
    print(f"  Total Size: {shared_size / 1024 / 1024:.2f} MB")
    
    print(f"\n📥 DOWNLOADED FILES")
    print(f"  Files: {download_count}")
    print(f"  Total Size: {download_size / 1024 / 1024:.2f} MB")


def main():
    """Main test menu."""
    if len(sys.argv) < 2:
        print_header("P2P FILE SHARING - TEST UTILITIES")
        print("""
Usage:  python test.py [command]

Commands:
  setup       - Create test files and directories
  check       - Check environment is set up correctly
  stats       - Show file statistics
  cleanup     - Delete downloaded test files
  help        - Show this help message

Examples:
  python test.py setup       # Create test files
  python test.py check       # Verify setup
  python test.py stats       # See current files
  python test.py cleanup     # Clean downloads
        """)
        return
    
    command = sys.argv[1].lower()
    
    if command == "setup":
        setup_test_environment()
    elif command == "check":
        check_environment()
    elif command == "stats":
        show_file_stats()
    elif command == "cleanup":
        cleanup_downloads()
    elif command == "help":
        print("Run: python test.py")
    else:
        print(f"Unknown command: {command}")
        print("Run: python test.py help")


if __name__ == "__main__":
    main()
