const API_BASE = '/api';

// =====================================================================
// INITIALIZATION
// =====================================================================

document.addEventListener('DOMContentLoaded', async () => {
    await loadStatus();
    await refreshSharedFiles();
    await refreshDownloadedFiles();
    await refreshConnectedPeers();
    await refreshPeers();

    setupUploadArea();
    setupSearch();

    // Refresh data periodically
    setInterval(refreshPeers, 10000);  // Every 10 seconds
    setInterval(refreshSharedFiles, 5000);  // Every 5 seconds
    setInterval(refreshConnectedPeers, 10000);  // Every 10 seconds
});

// =====================================================================
// STATUS & INITIALIZATION
// =====================================================================

async function loadStatus() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        const data = await response.json();

        document.getElementById('peer-id').textContent = data.peer_id;

        // Try to register with discovery
        try {
            await fetch(`${API_BASE}/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ port: data.port })
            });
        } catch (e) {
            console.log('Discovery service not available');
        }
    } catch (error) {
        console.error('Error loading status:', error);
        showNotification('Failed to load status', 'error');
    }
}

// =====================================================================
// FILE OPERATIONS
// =====================================================================

function setupUploadArea() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => {
            uploadArea.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => {
            uploadArea.classList.remove('dragover');
        });
    });

    uploadArea.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        fileInput.files = files;
        handleFileSelect();
    });

    fileInput.addEventListener('change', handleFileSelect);
}

async function handleFileSelect() {
    const fileInput = document.getElementById('fileInput');
    const files = fileInput.files;

    for (let file of files) {
        await uploadFile(file);
    }

    fileInput.value = '';
    await refreshSharedFiles();
}

async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const data = await response.json();
            showNotification(`✓ Uploaded: ${data.filename}`, 'success');
        } else {
            showNotification(`✗ Failed to upload: ${file.name}`, 'error');
        }
    } catch (error) {
        showNotification(`✗ Error uploading file: ${error.message}`, 'error');
    }
}

async function deleteSharedFile(filename) {
    if (!confirm(`Delete "${filename}" from shared files?`)) return;

    try {
        const response = await fetch(`${API_BASE}/shared/${filename}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showNotification(`✓ Deleted: ${filename}`, 'success');
            await refreshSharedFiles();
        }
    } catch (error) {
        showNotification(`✗ Error deleting file: ${error.message}`, 'error');
    }
}

async function deleteDownloadedFile(filename) {
    if (!confirm(`Delete "${filename}"?`)) return;

    try {
        const response = await fetch(`${API_BASE}/download/${filename}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showNotification(`✓ Deleted: ${filename}`, 'success');
            await refreshDownloadedFiles();
        }
    } catch (error) {
        showNotification(`✗ Error deleting file: ${error.message}`, 'error');
    }
}

async function refreshSharedFiles() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        const data = await response.json();

        const container = document.getElementById('sharedFiles');

        if (data.shared_files.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">📁</div>
                    <p>No files shared yet</p>
                </div>
            `;
            return;
        }

        container.innerHTML = data.shared_files.map(file => `
            <div class="file-item">
                <div class="file-info">
                    <div class="file-name">📄 ${escapeHtml(file.name)}</div>
                    <div class="file-size">${file.size_mb} MB</div>
                </div>
                <button class="btn btn-danger" onclick="deleteSharedFile('${escapeHtml(file.name)}')">Delete</button>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error refreshing shared files:', error);
    }
}

async function refreshDownloadedFiles() {
    try {
        const response = await fetch(`${API_BASE}/downloads`);
        const data = await response.json();

        const container = document.getElementById('downloadedFiles');

        if (data.downloads.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">📥</div>
                    <p>No files downloaded yet</p>
                </div>
            `;
            return;
        }

        container.innerHTML = data.downloads.map(file => `
            <div class="file-item">
                <div class="file-info">
                    <div class="file-name">✓ ${escapeHtml(file.name)}</div>
                    <div class="file-size">${file.size_mb} MB</div>
                </div>
                <button class="btn btn-danger" onclick="deleteDownloadedFile('${escapeHtml(file.name)}')">Delete</button>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error refreshing downloads:', error);
    }
}

// =====================================================================
// PEERS & SEARCH
// =====================================================================

async function refreshPeers() {
    try {
        const response = await fetch(`${API_BASE}/peers`);
        const data = await response.json();

        const container = document.getElementById('peersList');

        if (data.peers.length === 0) {
            container.innerHTML = `
                <div class="empty-state" style="grid-column: 1/-1;">
                    <div class="empty-icon">👥</div>
                    <p>No peers online</p>
                </div>
            `;
            return;
        }

        container.innerHTML = data.peers.map(peer => `
            <div class="peer-card">
                <div class="peer-title">🔗 ${escapeHtml(peer.peer_id)}</div>
                <div class="peer-detail">${escapeHtml(peer.ip)}:${peer.port}</div>
                <div class="peer-files">${peer.files} file(s)</div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error refreshing peers:', error);
    }
}

function setupSearch() {
    const searchInput = document.getElementById('searchInput');
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            searchFiles();
        }
    });
}

async function searchFiles() {
    const filename = document.getElementById('searchInput').value.trim();
    if (!filename) {
        showNotification('Please enter a filename', 'info');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/peers/search?filename=${encodeURIComponent(filename)}`);
        const data = await response.json();

        const container = document.getElementById('searchResults');

        if (data.error || data.found === 0) {
            container.innerHTML = `
                <div class="empty-state" style="margin-top: 20px;">
                    <div class="empty-icon">🔍</div>
                    <p>No peers found with this file</p>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <div style="margin-top: 20px;">
                <div style="font-weight: 600; margin-bottom: 12px; color: #333;">
                    Found on ${data.found} peer(s):
                </div>
                <div style="display: flex; flex-direction: column; gap: 10px;">
                    ${data.peers.map(peer => `
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #f8f9ff; border-radius: 8px; border-left: 4px solid #667eea;">
                            <div>
                                <div style="font-weight: 600; color: #333;">${escapeHtml(peer.peer_id)}</div>
                                <div style="font-size: 0.85em; color: #666; font-family: monospace; margin-top: 4px;">${escapeHtml(peer.ip)}:${peer.port}</div>
                            </div>
                            <button class="btn btn-primary" onclick="downloadFromPeer('${escapeHtml(filename)}', '${escapeHtml(peer.peer_id_full)}', '${escapeHtml(peer.ip)}', ${peer.port})">
                                Download
                            </button>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    } catch (error) {
        showNotification(`Error searching: ${error.message}`, 'error');
    }
}

async function downloadFromPeer(filename, peerId, ip, port) {
    try {
        const response = await fetch(`${API_BASE}/download`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: filename,
                peer_id: peerId,
                ip: ip,
                port: port
            })
        });

        if (response.ok) {
            showNotification(`⏳ Downloading ${filename}...`, 'info');

            // Poll progress
            const checkProgress = async () => {
                const progressResponse = await fetch(`${API_BASE}/download-progress/${encodeURIComponent(filename)}`);
                const progress = await progressResponse.json();

                if (progress.status === 'completed') {
                    showNotification(`✓ Download complete: ${filename}`, 'success');
                    await refreshDownloadedFiles();
                } else if (progress.status === 'failed') {
                    showNotification(`✗ Download failed: ${progress.error || 'Unknown error'}`, 'error');
                } else {
                    setTimeout(checkProgress, 500);
                }
            };

            setTimeout(checkProgress, 500);
        }
    } catch (error) {
        showNotification(`Error starting download: ${error.message}`, 'error');
    }
}

// =====================================================================
// UTILITIES
// =====================================================================

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// =====================================================================
// QR CODE FUNCTIONS
// =====================================================================

let cameraStream = null;
let qrScannerInterval = null;

async function openGenerateQRModal() {
    const modal = document.getElementById('generateQRModal');
    const overlay = document.getElementById('modalOverlay');
    
    modal.classList.remove('hidden');
    overlay.classList.remove('hidden');
    
    // Generate default QR (discovery mode)
    await updateQRMode();
}

async function updateQRMode() {
    const mode = document.querySelector('input[name="qrMode"]:checked').value;
    const full_mode = mode === 'direct';
    
    // Update description
    const description = full_mode 
        ? 'Dashboard URL for direct connection'
        : 'Requires discovery service lookup';
    document.getElementById('modeDescription').textContent = description;
    
    try {
        const response = await fetch(`${API_BASE}/qr/generate?full_mode=${full_mode}`);
        if (!response.ok) throw new Error('Failed to generate QR');
        
        const data = await response.json();
        document.getElementById('qrContainer').innerHTML = `
            <img src="${data.qr_image}" alt="QR Code" style="max-width: 300px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
        `;
        document.getElementById('qrLabelDisplay').value = data.qr_label;
        
        // Show URL field if in direct mode
        const urlContainer = document.getElementById('urlFieldContainer');
        const urlField = document.getElementById('connectionURLDisplay');
        if (data.dashboard_url) {
            urlContainer.style.display = 'block';
            urlField.value = data.dashboard_url;
        } else {
            urlContainer.style.display = 'none';
        }
    } catch (error) {
        document.getElementById('qrContainer').innerHTML = `
            <div style="color: #ff6b6b; padding: 20px;">Error generating QR: ${error.message}</div>
        `;
    }
}

function copyQRLabel() {
    const input = document.getElementById('qrLabelDisplay');
    input.select();
    document.execCommand('copy');
    showNotification('✓ QR label copied to clipboard', 'success');
}

function copyConnectionURL() {
    const input = document.getElementById('connectionURLDisplay');
    if (!input.value) {
        showNotification('URL not available', 'error');
        return;
    }
    input.select();
    document.execCommand('copy');
    showNotification('✓ Connection URL copied to clipboard', 'success');
}

function openConnectionURL(url) {
    window.open(url, '_blank');
    showNotification(`✓ Opening connection: ${url}`, 'success');
    setTimeout(() => {
        closeModal('scanQRModal');
    }, 1000);
}

function openScanQRModal() {
    const modal = document.getElementById('scanQRModal');
    const overlay = document.getElementById('modalOverlay');
    
    modal.classList.remove('hidden');
    overlay.classList.remove('hidden');
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    const overlay = document.getElementById('modalOverlay');
    
    modal.classList.add('hidden');
    overlay.classList.add('hidden');
    
    // Stop camera if open
    if (cameraStream) {
        stopCamera();
    }
}

function closeAllModals() {
    document.querySelectorAll('.modal').forEach(m => m.classList.add('hidden'));
    document.getElementById('modalOverlay').classList.add('hidden');
    
    if (cameraStream) {
        stopCamera();
    }
}

function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
        tab.classList.add('hidden');
    });
    
    // Deactivate all tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    const tab = document.getElementById(tabName + 'Tab');
    if (tab) {
        tab.classList.add('active');
        tab.classList.remove('hidden');
    }
    
    // Activate tab button
    event.target.classList.add('active');
}

function downloadQRCode() {
    const img = document.querySelector('#qrContainer img');
    if (!img) {
        showNotification('QR code not ready', 'error');
        return;
    }
    
    const link = document.createElement('a');
    link.href = img.src;
    link.download = 'peer-qr-code.png';
    link.click();
    showNotification('✓ QR code downloaded', 'success');
}

async function startCamera() {
    try {
        const constraints = {
            video: { facingMode: 'environment' },
            audio: false
        };
        
        cameraStream = await navigator.mediaDevices.getUserMedia(constraints);
        const video = document.getElementById('cameraFeed');
        video.srcObject = cameraStream;
        
        document.getElementById('startCameraBtn').style.display = 'none';
        document.getElementById('stopCameraBtn').style.display = 'inline-block';
        document.getElementById('webcamStatus').textContent = 'Camera active - Point at QR code';
        
        // Start QR scanning
        startQRScanning();
    } catch (error) {
        document.getElementById('webcamStatus').textContent = `Camera error: ${error.message}`;
        showNotification(`Camera error: ${error.message}`, 'error');
    }
}

function stopCamera() {
    if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
    }
    
    if (qrScannerInterval) {
        clearInterval(qrScannerInterval);
        qrScannerInterval = null;
    }
    
    document.getElementById('cameraFeed').srcObject = null;
    document.getElementById('startCameraBtn').style.display = 'inline-block';
    document.getElementById('stopCameraBtn').style.display = 'none';
    document.getElementById('webcamStatus').textContent = '';
}

function startQRScanning() {
    const video = document.getElementById('cameraFeed');
    const canvas = document.getElementById('canvasOverlay');
    const ctx = canvas.getContext('2d');
    
    // Set canvas size
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    
    qrScannerInterval = setInterval(() => {
        if (video.readyState === video.HAVE_ENOUGH_DATA) {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
            
            try {
                const code = jsQR(imageData.data, canvas.width, canvas.height);
                if (code) {
                    // Found QR code!
                    handleScannedQRCode(code.data);
                }
            } catch (error) {
                // Continue scanning
            }
        }
    }, 100);
}

async function handleScannedQRCode(data) {
    stopCamera();
    
    // Check if it's a URL
    if (data.startsWith('http://') || data.startsWith('https://')) {
        document.getElementById('webcamStatus').innerHTML = `
            <div style="padding: 15px; background: #f0f4ff; border-radius: 8px; text-align: center;">
                <div style="font-weight: 600; margin-bottom: 10px;">🔗 Connection Found</div>
                <div style="margin-bottom: 15px; font-family: monospace; color: #667eea; word-break: break-all; font-size: 0.9em;">
                    ${escapeHtml(data)}
                </div>
                <button class="btn btn-primary" onclick="openConnectionURL('${escapeHtml(data).replace(/'/g, "\\'")}')">
                    Connect Now
                </button>
            </div>
        `;
        return;
    }
    
    // Check if it's a full connection string (peer_id|ip|port)
    if (data.includes('|')) {
        const parts = data.split('|');
        if (parts.length === 3) {
            const [peer_id, ip, port] = parts;
            document.getElementById('webcamStatus').textContent = `Found peer: ${ip}:${port}`;
            await connectDirectPeer(peer_id, ip, parseInt(port));
            return;
        }
    }
    
    // Otherwise treat as peer_id only
    if (data.length !== 64 || !/^[0-9a-f]{64}$/i.test(data)) {
        showNotification('Invalid QR code - not a peer ID or URL', 'error');
        return;
    }
    
    document.getElementById('webcamStatus').textContent = `Found peer ID: ${data.substring(0, 16)}...`;
    await lookupAndAddPeer(data);
}

function handleQRDragOver(event) {
    event.preventDefault();
    event.stopPropagation();
    document.getElementById('uploadQRArea').classList.add('dragover');
}

function handleQRDragLeave(event) {
    event.preventDefault();
    event.stopPropagation();
    document.getElementById('uploadQRArea').classList.remove('dragover');
}

function handleQRDrop(event) {
    event.preventDefault();
    event.stopPropagation();
    document.getElementById('uploadQRArea').classList.remove('dragover');
    
    const files = event.dataTransfer.files;
    if (files.length > 0) {
        handleQRFileSelect({ target: { files: files } });
    }
}

async function handleQRFileSelect(event) {
    const files = event.target.files;
    if (files.length === 0) return;
    
    const file = files[0];
    
    try {
        const formData = new FormData();
        formData.append('file', file);
        
        document.getElementById('uploadQRArea').innerHTML = '<div class="spinner"></div>';
        
        const response = await fetch(`${API_BASE}/qr/decode`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(await response.text());
        }
        
        const data = await response.json();
        document.getElementById('uploadQRArea').innerHTML = `
            <div style="color: #4CAF50; padding: 20px;">
                <div style="font-size: 2em; margin-bottom: 10px;">✓</div>
                <div>QR code decoded</div>
            </div>
        `;
        
        // Handle different modes
        if (data.mode === 'dashboard_url') {
            // Display URL and provide connection button
            setTimeout(() => {
                document.getElementById('uploadQRArea').innerHTML = `
                    <div style="padding: 15px; background: #f0f4ff; border-radius: 8px; text-align: center;">
                        <div style="font-weight: 600; margin-bottom: 10px;">🔗 Connection Found</div>
                        <div style="margin-bottom: 15px; font-family: monospace; color: #667eea; word-break: break-all; font-size: 0.9em;">
                            ${escapeHtml(data.url)}
                        </div>
                        <button class="btn btn-primary" onclick="openConnectionURL('${escapeHtml(data.url).replace(/'/g, "\\'")}')">
                            Connect Now
                        </button>
                    </div>
                `;
            }, 500);
        } else if (data.mode === 'direct_connect') {
            await connectDirectPeer(data.peer_id, data.ip, data.port);
        } else {
            await lookupAndAddPeer(data.peer_id);
        }
    } catch (error) {
        document.getElementById('uploadQRArea').innerHTML = `
            <div style="color: #ff6b6b; padding: 20px;">
                <div>Error: ${error.message}</div>
            </div>
        `;
        showNotification(`Failed to decode QR: ${error.message}`, 'error');
    }
}

async function connectDirectPeer(peerId, ip, port) {
    try {
        const response = await fetch(`${API_BASE}/peers/connect`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                peer_id: peerId,
                ip: ip,
                port: port
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Connection failed');
        }
        
        const data = await response.json();
        showNotification(`✓ Connected to peer: ${ip}:${port}`, 'success');
        
        // Refresh both connected and online peers
        await refreshConnectedPeers();
        await refreshPeers();
        
        // Close modal after success
        setTimeout(() => {
            closeModal('scanQRModal');
        }, 1500);
    } catch (error) {
        showNotification(`Connection failed: ${error.message}`, 'error');
    }
}

async function refreshConnectedPeers() {
    try {
        const response = await fetch(`${API_BASE}/peers/connected`);
        const data = await response.json();
        
        const container = document.getElementById('connectedPeersList');
        if (!container) return; // Element doesn't exist yet
        
        if (data.connected_peers.length === 0) {
            container.innerHTML = `
                <div class="empty-state" style="grid-column: 1/-1;">
                    <div class="empty-icon">🔗</div>
                    <p>No connected peers</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = data.connected_peers.map(peer => `
            <div class="peer-card" style="border: 2px solid #4CAF50; background: linear-gradient(135deg, rgba(76, 175, 80, 0.1) 0%, rgba(76, 175, 80, 0.05) 100%);">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                    <span style="font-size: 1.2em;">🟢</span>
                    <div class="peer-title" style="margin: 0;">${escapeHtml(peer.peer_id_short)}</div>
                </div>
                <div class="peer-detail">${escapeHtml(peer.ip)}:${peer.port}</div>
                <div style="font-size: 0.8em; color: #4CAF50; margin-top: 8px; font-weight: 600;">✓ Connected</div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error refreshing connected peers:', error);
    }
}

async function lookupAndAddPeer(peerId) {
    try {
        const response = await fetch(`${API_BASE}/peers/lookup?peer_id=${encodeURIComponent(peerId)}`);
        
        if (!response.ok) {
            throw new Error('Peer not found in discovery service');
        }
        
        const data = await response.json();
        const peer = data.peer;
        
        // Show confirmation and add to UI
        showNotification(`✓ Found peer: ${peer.peer_id_short}`, 'success');
        
        // Refresh peers to show the newly discovered peer
        await refreshPeers();
        
        // Close modal after success
        setTimeout(() => {
            closeModal('scanQRModal');
        }, 1500);
    } catch (error) {
        showNotification(`Could not find peer: ${error.message}`, 'error');
    }
}
