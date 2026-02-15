# P2P File Sharing System - Complete Documentation

## Table of Contents
1. [Quick Start](#quick-start)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Running the System](#running-the-system)
5. [Web Dashboard](#web-dashboard)
6. [Security & Protocol](#security--protocol)
7. [API Reference](#api-reference)
8. [Troubleshooting](#troubleshooting)
9. [Advanced Configuration](#advanced-configuration)

---

## Quick Start

### 30-Second Setup
```bash
# 1. Create test files
python test.py setup

# 2. Start everything
python run.py

# 3. Open browser
# → http://localhost:8080
```

### Required Dependencies
```bash
pip install fastapi uvicorn httpx cryptography python-multipart
```

---

## Features

- **🔐 Secure**: Hybrid RSA-2048 + AES-256-GCM encryption
- **⚡ Fast**: 4 concurrent chunk downloads (configurable up to 16)
- **✓ Reliable**: SHA-256 verification on all downloads
- **📦 Scalable**: Large files split into 1MB chunks (configurable)
- **🌐 Decentralized**: Direct peer-to-peer transfers after discovery
- **🔄 Auto-Registration**: Peers register and send heartbeats automatically
- **🌟 Modern UI**: Beautiful web dashboard with real-time updates
- **📱 Mobile-Friendly**: Responsive design works on all devices

---

## Architecture

```
┌─────────────────────────────────────────┐
│      DISCOVERY SERVICE (Port 8000)      │
│  ◆ Central peer registry                │
│  ◆ Responds to peer queries             │
│  ◆ Maintains heartbeat list             │
└─────────────────────────────────────────┘
        ↑              ↑              ↑
       │ query        │ register      │ query
       │ peers        │ heartbeat     │ peers
        │              │              │
   ┌────┴──────┐  ┌────┴──────┐  ┌────┴──────┐
   │   PEER A  │  │   PEER B  │  │   PEER C  │
   │ Server    │  │ Server    │  │ Server    │
   │ Port 9000 │  │ Port 9000 │  │ Port 9000 │
   │ Shares    │  │ Shares    │  │ Shares    │
   │ files     │  │ files     │  │ files     │
   └────┬──────┘  └────┬──────┘  └────┬──────┘
        │              │              │
        └──────────────┼──────────────┘
        P2P Direct Transfers (Encrypted)
```

### Component Overview

| Component | Purpose | Port |
|-----------|---------|------|
| **main.py** | Discovery Service | 8000 |
| **server.py** | Peer File Server | 9000 |
| **client.py** | Download Client | - |
| **ui/api.py** | Web API Backend | 8080 |
| **crypto.py** | RSA + AES Encryption | - |
| **identity.py** | Key Management | - |
| **chunk_manager.py** | File Chunking | - |

---

## Running the System

### Option 1: All-in-One (Recommended)
```bash
python run.py
```
Starts discovery + peer server + web UI with auto-registration.

**Access**: http://localhost:8080

### Option 2: Components Separately

**Terminal 1 - Discovery Service:**
```bash
python peer/main.py
```

**Terminal 2 - Peer Server:**
```bash
python peer/server.py
```

**Terminal 3 - Web UI:**
```bash
uvicorn ui.api:app --host 0.0.0.0 --port 8080
```

### Option 3: Multi-Peer Testing

```bash
# Terminal 1
python run.py

# Terminal 2 (different port)
python peer/runner.py --mode peer --peer-port 9001 --shared-dir shared_b

# Terminal 3 (optional)
python peer/runner.py --mode peer --peer-port 9002 --shared-dir shared_c
```

---

## Web Dashboard

### URL
```
http://localhost:8080
http://<your-ip>:8080  (from other computers)
```

### Features

#### 1. Share Files Section
- Drag & drop file upload
- Automatic list refresh
- File size display
- Quick delete option

#### 2. Online Peers
- Real-time peer discovery
- Shows peer ID, IP, port, file count
- Manual refresh button (🔄)
- Auto-refresh every 10 seconds

#### 3. Search & Download
- Search files across network
- Shows all peers with that file
- Download with one click
- Real-time progress indicator

#### 4. Downloaded Files
- Lists all successfully downloaded files
- File size display
- Quick delete option
- Auto-refresh every 5 seconds

### How to Use Dashboard

#### Upload Files
1. Click "Choose Files" or drag files
2. Select file(s) from your computer
3. Files appear in "Shared Files" list
4. Now other peers can find and download them

#### Download Files
1. Type filename in search box
2. Press Enter or click "Search"
3. List shows all peers with that file
4. Click "Download" on desired peer
5. Progress updates in real-time
6. File appears in "Downloaded Files" when complete

#### Mobile Access
1. On desktop: `python run.py`
2. Find your computer's IP: `ipconfig` (Windows)
3. On phone: Open `http://<your-ip>:8080`
4. Same dashboard, full functionality

---

## Security & Protocol

### Key Exchange (Handshake)
```
Client                                      Server
  │
  ├─ HELLO: {peer_id, public_key} ────────→ Server reads public key
  │                                          Server generates AES-256 key
  │                                          Server encrypts with client's RSA key
  ├──← SESSION: {encrypted_aes_key} ──────  Client decrypts with private key
  │
  └──× Both have shared AES key ─────────→ Switch to encrypted channel
```

### File Transfer (Encrypted)
```
Client                                      Server
  │
  ├─ META: {filename} ────────────────────→ Server reads file metadata
  ├─← META: {size, chunks, hash} ────────  Client knows what to expect
  │
  ├─ GET: {filename, chunk_0} ───────────→ Server encrypts chunk 0
  ├─← CHUNK: {encrypted_data} ──────────  Client decrypts with AES key
  │
  ├─ GET: {filename, chunk_1} ───────────→ (parallel)
  ├─← CHUNK: {encrypted_data} ──────────  (4 connections at once)
  │
  ├─ GET: {filename, chunk_2} ───────────→ (parallel)
  ├─← CHUNK: {encrypted_data} ──────────  (parallel)
  │
  └──× Reassemble chunks ────────────────→ Verify SHA256 hash
       Save to disk
```

### Encryption Details

**RSA-2048 (Key Exchange)**
- 2048-bit key length
- PKCS8 format for storage
- Used only for initial handshake

**AES-256-GCM (Data Transfer)**
- 256-bit key length
- 12-byte random nonce per message
- Authenticated encryption (built-in integrity)
- Stream encryption for chunks

**SHA-256 (Integrity)**
- 256-bit hash
- Computed on complete file
- Verified after all chunks reassembled

---

## API Reference

### Base URL
```
http://localhost:8080/api
```

### Endpoints

#### GET `/`
- **Description**: Serve UI dashboard
- **Returns**: HTML page
- **Auth**: None

#### GET `/api/status`
- **Description**: Get your peer status
- **Returns**: Peer ID, port, shared files list
- **Response**: 
```json
{
  "peer_id": "a1b2c3d4...",
  "peer_id_full": "a1b2c3d4f5e6...",
  "port": 9000,
  "registered": true,
  "shared_files": [
    {"name": "file.txt", "size": 1024, "size_mb": 0.001}
  ],
  "shared_files_count": 1,
  "total_shared_size": 1024
}
```

#### GET `/api/peers`
- **Description**: Get list of online peers
- **Returns**: Array of peer objects with file counts
- **Response**: 
```json
{
  "peers": [
    {
      "peer_id": "9f8e7d6c...",
      "ip": "192.168.1.100",
      "port": 9000,
      "files": 5
    }
  ]
}
```

#### GET `/api/peers/search?filename=X`
- **Description**: Search for peers with specific file
- **Parameters**: `filename` (URL encoded)
- **Returns**: List of peers with that file
- **Response**: 
```json
{
  "filename": "largefile.zip",
  "found": 2,
  "peers": [
    {
      "peer_id": "a1b2...",
      "peer_id_full": "a1b2c3d4...",
      "ip": "192.168.1.100",
      "port": 9000
    }
  ]
}
```

#### POST `/api/upload`
- **Description**: Upload file to shared directory
- **Content-Type**: `multipart/form-data`
- **Parameters**: `file` (binary file)
- **Returns**: Upload status
- **Response**: 
```json
{
  "status": "success",
  "filename": "myfile.txt",
  "size": 2048,
  "size_mb": 0.002
}
```

#### POST `/api/download`
- **Description**: Start downloading from peer
- **Content-Type**: `application/json`
- **Body**: 
```json
{
  "filename": "file.txt",
  "peer_id": "a1b2c3d4...",
  "ip": "192.168.1.100",
  "port": 9000
}
```
- **Returns**: Download started
- **Response**: 
```json
{
  "status": "downloading",
  "filename": "file.txt",
  "peer": "192.168.1.100:9000"
}
```

#### GET `/api/download-progress/{filename}`
- **Description**: Check download progress
- **Returns**: Current progress status
- **Response**: 
```json
{
  "status": "downloading",
  "progress": 45,
  "peer": "192.168.1.100:9000"
}
```
Status values: `downloading`, `completed`, `failed`

#### GET `/api/downloads`
- **Description**: List downloaded files
- **Returns**: Array of downloaded file objects
- **Response**: 
```json
{
  "downloads": [
    {"name": "file.txt", "size": 2048, "size_mb": 0.002}
  ]
}
```

#### POST `/api/register`
- **Description**: Register peer with discovery service
- **Content-Type**: `application/json`
- **Body**: 
```json
{
  "port": 9000
}
```
- **Returns**: Registration confirmation
- **Response**: 
```json
{
  "status": "registered",
  "peer_id": "a1b2c3d4...",
  "port": 9000
}
```

#### DELETE `/api/shared/{filename}`
- **Description**: Delete file from shared directory
- **Parameters**: `filename` (URL encoded)
- **Returns**: Deletion confirmation
- **Response**: 
```json
{
  "status": "deleted",
  "filename": "file.txt"
}
```

#### DELETE `/api/download/{filename}`
- **Description**: Delete downloaded file
- **Parameters**: `filename` (URL encoded)
- **Returns**: Deletion confirmation
- **Response**: 
```json
{
  "status": "deleted",
  "filename": "file.txt"
}
```

---

## Troubleshooting

### Port Already in Use
```
Error: [Errno 48] Address already in use
```
Change the port:
```bash
python peer/runner.py --mode peer --peer-port 9001
```

### Peer Not Appearing in List
- Check discovery service is running
- Check firewall allows port 8000
- Verify peer sent heartbeat (check logs)

### Connection Refused
```
ConnectionRefusedError: [Errno 111] Connection refused
```
- Is peer server running on port 9000?
- Check IP address is correct
- Verify no firewall blocking

### File Download Fails
**Hash mismatch**: Network error mid-transfer
- Click search and download again
- Try different peer if available

**Timeout error**: File too large or network slow
- Increase `TIMEOUT` in `peer/client.py`
- Use fewer concurrent chunks (slower but more reliable)

### Slow Downloads
- Increase `MAX_CONCURRENT_CHUNKS` in `peer/client.py`
- Increase `CHUNK_SIZE` for better throughput
- Check internet connection speed

### Discovery Service Not Found
```
Error: Cannot connect to http://localhost:8000
```
Make sure to start discovery service:
```bash
python peer/main.py
```

---

## Advanced Configuration

### Increase Concurrent Chunks

Edit [peer/client.py](peer/client.py):
```python
MAX_CONCURRENT_CHUNKS = 8  # Default: 4, Max recommended: 16
```

**Trade-offs:**
- Higher = faster downloads but more connections
- Lower = slower but fewer resources

### Adjust Chunk Size

Edit [peer/chunk_manager.py](peer/chunk_manager.py):
```python
CHUNK_SIZE = 2 * 1024 * 1024  # Default: 1MB, try 2-10MB for LAN
```

**Trade-offs:**
- Larger = faster on good networks
- Smaller = better for unstable/high-latency networks

### Change Heartbeat Interval

Edit [peer/runner.py](peer/runner.py):
```python
await heartbeat_loop(discovery_url, peer_id, interval=60)  # Default: 30 seconds
```

**Effects:**
- Lower interval = peers disappear slower when offline
- Higher interval = less discovery traffic

### Custom Directories

```bash
# Share from different directory
python peer/runner.py --mode peer --shared-dir /path/to/share

# Download to different directory
python peer/client.py --output-dir /path/to/downloads
```

### Change Network Ports

```bash
# Different discovery port
python peer/main.py --port 8001

# Different peer server port
python peer/runner.py --mode peer --peer-port 9001

# Different UI port
uvicorn ui.api:app --port 8081
```

---

## Performance Tuning

### For High-Latency Networks (WAN)
```python
MAX_CONCURRENT_CHUNKS = 16  # Increase parallelism
CHUNK_SIZE = 256 * 1024  # Smaller chunks
TIMEOUT = 60  # Longer timeout
```

### For LAN Networks
```python
MAX_CONCURRENT_CHUNKS = 4  # Standard parallelism
CHUNK_SIZE = 5 * 1024 * 1024  # Larger chunks
TIMEOUT = 10  # Quick timeout
```

### Large File Transfers (> 1GB)
```python
MAX_CONCURRENT_CHUNKS = 2  # Reduce to manage memory
CHUNK_SIZE = 10 * 1024 * 1024  # Large chunks
```

---

## File Structure

```
Fileshare/
├── peer/                      # Core P2P system
│   ├── main.py               # Discovery service
│   ├── server.py             # Peer server
│   ├── client.py             # Download client
│   ├── crypto.py             # Encryption
│   ├── identity.py           # Key management
│   ├── chunk_manager.py      # Chunking
│   ├── protocol.py           # Message types
│   └── runner.py             # CLI launcher
│
├── ui/                        # Web dashboard
│   ├── __init__.py           # Package init
│   ├── api.py                # FastAPI app
│   ├── templates.py          # HTML template
│   ├── config.py             # Configuration
│   └── state.py              # State management
│
├── keys/                      # Auto-generated keys
│   ├── private_key.pem
│   └── public_key.pem
│
├── shared/                    # Files to share
├── downloads/                 # Downloaded files
│
├── run.py                     # Main launcher
├── test.py                    # Testing utilities
├── demo.py                    # Interactive demo
└── DOCS.md                    # This file
```

---

## Security Checklist

- ✅ RSA-2048 encryption for key exchange
- ✅ AES-256-GCM for data transfer
- ✅ SHA-256 file integrity verification
- ✅ Unique peer IDs from public key hash
- ✅ Per-connection session keys
- ⚠️ No peer authentication (trust public keys from discovery)
- ⚠️ No bandwidth limiting
- ⚠️ No rate limiting

---

## Known Limitations

- Single-threaded peer server (max ~10 concurrent clients)
- No compression support
- No partial/resume downloads
- No peer authentication (discovery-based trust)
- No bandwidth limiting
- Keys stored in plaintext (no password protection)

---

## Future Enhancements

- [ ] Multi-threaded peer server
- [ ] Peer authentication with digital signatures
- [ ] Bandwidth limiting (QoS)
- [ ] Resume/partial downloads
- [ ] File compression
- [ ] mDNS auto-discovery
- [ ] Redis caching for metadata
- [ ] WebRTC for NAT traversal
- [ ] File versioning system
- [ ] Redundancy/mirroring across peers

---

## Getting Help

### Check Logs
Add debug logging to see what's happening:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Test Connectivity
```bash
# Can you reach the discovery service?
python -c "import httpx; print(httpx.get('http://localhost:8000/peers').json())"

# Can you reach a peer?
python -c "import socket; s = socket.socket(); s.connect(('127.0.0.1', 9000))"
```

### Verify Encryption
Download a file and check:
```bash
# Should have specific size based on file
ls -lh downloads/
```

---

**Last Updated**: February 2026  
**Status**: Production Ready ✓

