"""
Simple demo script showing the file sharing system in action.
Shows the complete flow from registration through download.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add peer directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'peer'))


async def create_test_file():
    """Create a test file to share."""
    os.makedirs("shared", exist_ok=True)
    
    # Create a test file
    test_content = "Hello from P2P File Sharing System!\n" * 100
    with open("shared/test.txt", "w") as f:
        f.write(test_content)
    
    print(f"✓ Created test file: shared/test.txt ({len(test_content)} bytes)")


def print_header(title):
    """Print a section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")


async def demo():
    """Run a complete demo of the file sharing system."""
    
    print_header("P2P FILE SHARING SYSTEM - DEMO")
    
    print("This demo shows the complete flow of the file sharing system.")
    print("It requires running the system in different terminals.\n")
    
    print("STEP 1: Create test file")
    print("-" * 60)
    await create_test_file()
    print()
    
    print("STEP 2: Start the discovery service")
    print("-" * 60)
    print("Run in Terminal 1:")
    print("  python peer/runner.py --mode discovery --discovery-port 8000")
    print()
    
    print("STEP 3: Start a peer server")
    print("-" * 60)
    print("Run in Terminal 2:")
    print("  python peer/runner.py --mode peer --peer-port 9000 --shared-dir shared")
    print()
    print("This will:")
    print("  • Register with the discovery service")
    print("  • Share files from the 'shared' directory")
    print("  • Send heartbeats every 30 seconds")
    print()
    
    print("STEP 4: Download file from another peer")
    print("-" * 60)
    print("Run in Terminal 3:")
    print("  python peer/runner.py --mode client --download-file test.txt")
    print()
    print("This will:")
    print("  • Query the discovery service for peers with 'test.txt'")
    print("  • Connect to the peer server")
    print("  • Download chunks concurrently (4 at a time)")
    print("  • Verify file integrity with SHA-256")
    print("  • Save to downloads/ directory")
    print()
    
    print("STEP 5: View the architecture")
    print("-" * 60)
    print("""
DISCOVERY SERVICE (central registry)
    ↑                          ↑
    │  register + heartbeat    │  query
    │                          │
  PEER A                      PEER B
  Server                      Server
  (sharing files)             (downloading files)
    ↓                          ↓
  [files]                    ← ← ← (direct P2P transfer)
  (shared/)
    """)
    print()
    
    print("KEY FEATURES")
    print("-" * 60)
    print("✓ Secure: RSA + AES-256 hybrid encryption")
    print("✓ Fast: Concurrent chunk downloads (4 parallel by default)")
    print("✓ Reliable: SHA-256 integrity verification")
    print("✓ Scalable: Files split into 1MB chunks")
    print("✓ Decentralized: Direct P2P transfers (discovery is optional)")
    print()
    
    print("PROTOCOL FLOW")
    print("-" * 60)
    print("""
1. PEER DISCOVERY
   Peer → Discovery: POST /register {peer_id, public_key, port, files}
   Peer → Discovery: GET /heartbeat (every 30 sec)
   Other Peers → Discovery: GET /peers?file=filename (find peers)

2. SECURE HANDSHAKE
   Client → Server: HELLO | peer_id | public_key
   Server → Client: SESSION | AES_key_encrypted_with_RSA

3. FILE TRANSFER (encrypted with AES-256-GCM)
   Client → Server: META | filename
   Server → Client: file_size, chunk_count, SHA256_hash
   
   (Multiple in parallel)
   Client → Server: GET | filename | chunk_index
   Server → Client: CHUNK | chunk_index | chunk_data
   
   Client → Server: DONE

4. VERIFICATION
   Client: Reassemble chunks in order
   Client: Verify SHA-256 hash matches
    """)
    print()
    
    print("FILE STRUCTURE")
    print("-" * 60)
    print("""
Fileshare/
├── keys/                    # RSA key pairs (auto-generated)
│   ├── private_key.pem
│   └── public_key.pem
├── peer/
│   ├── main.py             # Discovery service (FastAPI)
│   ├── server.py           # Peer server (handles requests)
│   ├── client.py           # Peer client (downloads files)
│   ├── crypto.py           # RSA + AES encryption
│   ├── identity.py         # Key management & peer IDs
│   ├── chunk_manager.py    # File chunking & metadata
│   ├── protocol.py         # Message types (HELLO, SESSION, etc)
│   ├── runner.py           # Integrated runner (all modes)
│   └── __pycache__/
├── shared/                 # Files to share (configurable)
│   └── test.txt
├── downloads/              # Downloaded files
└── USAGE.md               # Detailed usage guide
    """)
    print()
    
    print("NEXT STEPS")
    print("-" * 60)
    print("1. See USAGE.md for detailed command-line options")
    print("2. Adjust MAX_CONCURRENT_CHUNKS in client.py for performance")
    print("3. Try multi-peer setup with different ports")
    print("4. Monitor heartbeats in discovery service logs")
    print()


if __name__ == "__main__":
    asyncio.run(demo())
