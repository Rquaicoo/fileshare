const API_BASE = '/api';

// =====================================================================
// INITIALIZATION
// =====================================================================

document.addEventListener('DOMContentLoaded', async () => {
    await loadStatus();
    await refreshSharedFiles();
    await refreshDownloadedFiles();
    await refreshPeers();

    setupUploadArea();
    setupSearch();

    // Refresh data periodically
    setInterval(refreshPeers, 10000);  // Every 10 seconds
    setInterval(refreshSharedFiles, 5000);  // Every 5 seconds
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
