#!/usr/bin/env python3
"""
Simple test to verify file download works.
"""

import asyncio
import os
import sys
import hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from peer.server import start_server
from peer.client import connect_to_peer
from peer.chunk_manager import get_file_metadata


async def test_simple_download():
    """Test a simple file download."""
    
    # Create test file
    os.makedirs("shared", exist_ok=True)
    test_file = "shared/test_simple.txt"
    test_content = b"Hello, World! This is a test.\n" * 10
    
    with open(test_file, "wb") as f:
        f.write(test_content)
    
    print("✓ Created test file")
    
    # Start server with timeout
    server_task = asyncio.create_task(start_server(19001, "shared"))
    await asyncio.sleep(0.5)
    
    try:
        # Download file
        os.makedirs("downloads", exist_ok=True)
        result = await asyncio.wait_for(
            connect_to_peer("127.0.0.1", 19001, "test_simple.txt", "downloads"),
            timeout=10
        )
        
        if result:
            print("✓ Download completed")
            
            # Verify
            with open("downloads/test_simple.txt", "rb") as f:
                downloaded = f.read()
            
            if downloaded == test_content:
                print("✓ Content verified")
                return True
            else:
                print("✗ Content mismatch")
                return False
        else:
            print("✗ Download failed")
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    finally:
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    try:
        result = asyncio.run(test_simple_download())
        print()
        if result:
            print("=" * 50)
            print("✅ DOWNLOAD TEST PASSED!")
            print("=" * 50)
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
