# File Download Fix - Summary

## Problem
File downloads were failing due to **improper socket message framing** in the peer-to-peer file transfer protocol.

## Root Cause
When the server sent encrypted chunks to the client, the client used `reader.read(1024*1024+100)` which returns **UP TO** that many bytes, not exactly that many. If encrypted data was split across multiple TCP packets, the client would receive incomplete encrypted data and fail to decrypt it.

### Example of the issue:
```
Client: await reader.read(1024 * 1024 + 100)  # May return only 5KB
Server: (sends 500KB encrypted chunk split across multiple packets)
Result: Decryption fails because only partial encrypted data was read
```

## Solution
Implemented **length-prefixed message framing** for all encrypted messages:

1. **Each message now includes a 4-byte length prefix** indicating the encrypted data size
2. **Client uses `readexactly()`** to read exactly the specified number of bytes
3. **Server prepends message length** before sending encrypted data

### Message Format (Before):
```
[encrypted_data]  (no way to know when to stop reading)
```

### Message Format (After):
```
[4-byte length][encrypted_data]  (client knows exactly how many bytes to read)
```

## Files Modified

### 1. [peer/client.py](peer/client.py)

**Function: `get_file_metadata()`**
- Added length prefix to META request
- Uses `readexactly()` to read length-prefixed metadata response
- Ensures complete metadata is received before decryption

**Function: `download_single_chunk()`**  
- Added length prefix to GET request
- Uses `readexactly()` to read length-prefixed chunk response
- Handles `asyncio.IncompleteReadError` for better error detection

### 2. [peer/server.py](peer/server.py)

**Function: `handle_peer()`**
- Fixed bug: was passing PEM bytes directly to `encrypt_session_key()`
- Now properly loads public key using `serialization.load_pem_public_key()`

**Function: `serve_file()`**
- Changed from `reader.read(4096)` to `reader.readexactly()`
- Reads 4-byte length prefix to determine message size
- Sends all responses with length prefix
- Handles `asyncio.IncompleteReadError` for disconnections

## Technical Details

### Cryptography Flow (unchanged)
1. Peer A sends HELLO with peer_id and public key
2. Peer B generates AES key and encrypts it with A's public key
3. Peer B sends SESSION with encrypted key
4. Both peers use AES-256-GCM for further communication

### Message Protocol (improved)
```
Request:  [4-byte length][encrypted: "META|filename"]
Response: [4-byte length][nonce(12) + AES-encrypted data]
```

## Testing
Created test script [test_download_simple.py](test_download_simple.py) that verifies:
- ✅ File creation
- ✅ Server handshake
- ✅ Metadata retrieval
- ✅ Chunk download
- ✅ File reassembly
- ✅ Content verification (SHA-256)

## Verification
Run the test:
```bash
python test_download_simple.py
```

Or run the full system:
```bash
python run.py
```

Then use the web dashboard at http://localhost:8080 to upload and download files.

## Performance Impact
- **Positive**: Proper message framing ensures reliability
- **Negligible**: 4-byte length prefix adds minimal overhead
- **Same**: Encryption/decryption performance unchanged

## Backward Compatibility
⚠️ **Breaking Change**: Old clients cannot communicate with updated servers (and vice versa)
- Both client and server must be updated together
- Uses new length-prefixed message format throughout

## Additional Notes
- Socket timeouts are preserved (10s for connection, 30s for read)
- Concurrent chunk downloads still work (4 parallel by default)
- File integrity verification (SHA-256) unchanged
- Encryption strength unchanged (RSA-2048 + AES-256-GCM)
