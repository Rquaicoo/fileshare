#!/usr/bin/env python3
"""
Test script to verify the file download fix.
Tests the complete download flow with proper message framing.
"""

import asyncio
import os
import sys
import hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from peer.server import start_server
from peer.client import connect_to_peer
from peer.chunk_manager import get_file_metadata, CHUNK_SIZE
from test import create_test_files, create_large_file


async def run_test():
    """Run a complete download test."""
    
    print("=" * 70)
    print("P2P FILE SHARING - DOWNLOAD TEST")
    print("=" * 70)
    
    # Setup
    print("\n1. Creating test files...")
    os.makedirs("shared", exist_ok=True)
    os.makedirs("downloads", exist_ok=True)
    os.makedirs("keys", exist_ok=True)
    
    # Create a test file (use binary mode for consistent results)
    test_filename = "test_download.txt"
    test_content = b"This is a test file for download.\n" * 100
    test_path = os.path.join("shared", test_filename)
    
    with open(test_path, "wb") as f:
        f.write(test_content)
    
    print(f"   ✓ Created test file: {test_filename} ({len(test_content)} bytes)")
    
    # Get metadata
    print("\n2. Computing file metadata...")
    meta = get_file_metadata(test_path)
    print(f"   ✓ File size: {meta['size']} bytes")
    print(f"   ✓ Chunk size: {meta['chunksize']} bytes")
    print(f"   ✓ Total chunks: {meta['chunks']}")
    print(f"   ✓ SHA256: {meta['hash'][:16]}...")
    
    # Start server in background
    print("\n3. Starting peer server on port 19000...")
    server_task = asyncio.create_task(start_server(19000, "shared"))
    await asyncio.sleep(1)  # Wait for server to start
    print("   ✓ Server started")
    
    # Download file
    print(f"\n4. Downloading {test_filename} from 127.0.0.1:19000...")
    success = False
    try:
        success = await asyncio.wait_for(
            connect_to_peer("127.0.0.1", 19000, test_filename, "downloads"),
            timeout=30
        )
        
        if success:
            print("   ✓ Download completed successfully")
            
            # Verify
            print("\n5. Verifying downloaded file...")
            downloaded_path = os.path.join("downloads", test_filename)
            
            if os.path.exists(downloaded_path):
                with open(downloaded_path, "rb") as f:
                    downloaded_content = f.read()
                
                downloaded_hash = hashlib.sha256(downloaded_content).hexdigest()
                
                if downloaded_hash == meta['hash']:
                    print(f"   ✓ File verified (hash matches)")
                    print(f"   ✓ Downloaded size: {len(downloaded_content)} bytes")
                    
                    if downloaded_content == test_content:
                        print(f"   ✓ Content matches perfectly")
                        print("\n" + "=" * 70)
                        print("✅ ALL TESTS PASSED - Download mechanism works correctly!")
                        print("=" * 70)
                        success = True
                    else:
                        print(f"   ✗ Content mismatch")
                        print(f"      Expected {len(test_content)} bytes, got {len(downloaded_content)} bytes")
                        success = False
                else:
                    print(f"   ✗ Hash mismatch!")
                    print(f"      Expected: {meta['hash']}")
                    print(f"      Got:      {downloaded_hash}")
                    success = False
            else:
                print(f"   ✗ Downloaded file not found")
                success = False
        else:
            print("   ✗ Download failed")
            success = False
            
    except asyncio.TimeoutError:
        print("   ✗ Download timed out")
        success = False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        success = False
    
    finally:
        try:
            server_task.cancel()
        except:
            pass
        
        if not success:
            print("\n" + "=" * 70)
            print("❌ TEST FAILED - See errors above")
            print("=" * 70)
        
    return success
