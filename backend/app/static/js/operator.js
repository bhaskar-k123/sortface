/**
 * Operator Panel JavaScript
 * Handles job configuration, person seeding, and job control
 */

// Global state for selected persons
let selectedPersonIds = new Set();

document.addEventListener('DOMContentLoaded', () => {
    // Load existing data
    loadPersons();
    loadPersonSelection();
    loadJobConfig();
    loadJobStatus();
    
    // Check status periodically
    checkWorkerStatus();
    setInterval(checkWorkerStatus, 3000);
    setInterval(loadJobStatus, 3000);
    
    // Setup form handlers
    setupJobConfigForm();
    setupSeedPersonForm();
});

/**
 * Load and display registered persons
 */
async function loadPersons() {
    const container = document.getElementById('persons-list');
    
    try {
        const response = await fetch('/api/operator/persons');
        const data = await response.json();
        
        if (data.persons && data.persons.length > 0) {
            container.innerHTML = data.persons.map(person => `
                <div class="person-card">
                    <button class="delete-btn" onclick="deletePerson(${person.person_id}, '${escapeHtml(person.name)}')" title="Delete person">🗑️</button>
                    <div class="person-avatar">
                        <img src="/api/operator/persons/${person.person_id}/thumbnail" 
                             alt="${escapeHtml(person.name)}"
                             onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                        <div class="avatar-placeholder" style="display:none;">👤</div>
                    </div>
                    <div class="name">${escapeHtml(person.name)}</div>
                    <div class="folder">📁 ${escapeHtml(person.output_folder_rel)}</div>
                    <div class="embeddings">${person.embedding_count} reference(s)</div>
                    <div class="add-ref-section">
                        <label class="add-ref-label" for="ref-input-${person.person_id}">
                            ➕ Add more references (select multiple)
                        </label>
                        <input type="file" id="ref-input-${person.person_id}" class="add-ref-input"
                               accept=".jpg,.jpeg,.png" multiple 
                               onchange="addMultipleReferences(${person.person_id}, this)">
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<p class="loading">No persons registered yet</p>';
        }
    } catch (error) {
        container.innerHTML = '<p class="loading">Error loading persons</p>';
        console.error('Error loading persons:', error);
    }
}

/**
 * Load person selection checkboxes for job configuration
 */
async function loadPersonSelection() {
    const container = document.getElementById('person-selection-list');
    
    try {
        const response = await fetch('/api/operator/persons');
        const data = await response.json();
        
        if (data.persons && data.persons.length > 0) {
            container.innerHTML = data.persons.map(person => `
                <label class="person-select-item ${selectedPersonIds.has(person.person_id) ? 'selected' : ''}"
                       onclick="togglePersonSelection(${person.person_id}, this)">
                    <input type="checkbox" 
                           id="select-person-${person.person_id}" 
                           value="${person.person_id}"
                           ${selectedPersonIds.has(person.person_id) ? 'checked' : ''}>
                    <img src="/api/operator/persons/${person.person_id}/thumbnail" 
                         class="thumb" alt=""
                         onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                    <span class="thumb-placeholder" style="display:none;">👤</span>
                    <span class="select-name">${escapeHtml(person.name)}</span>
                </label>
            `).join('');
        } else {
            container.innerHTML = '<p class="loading">No persons registered. Add persons first.</p>';
        }
    } catch (error) {
        container.innerHTML = '<p class="loading">Error loading persons</p>';
        console.error('Error loading person selection:', error);
    }
}

/**
 * Toggle person selection
 */
function togglePersonSelection(personId, element) {
    const checkbox = element.querySelector('input[type="checkbox"]');
    
    if (selectedPersonIds.has(personId)) {
        selectedPersonIds.delete(personId);
        element.classList.remove('selected');
        checkbox.checked = false;
    } else {
        selectedPersonIds.add(personId);
        element.classList.add('selected');
        checkbox.checked = true;
    }
}

/**
 * Select all persons
 */
function selectAllPersons() {
    document.querySelectorAll('.person-select-item').forEach(item => {
        const checkbox = item.querySelector('input[type="checkbox"]');
        const personId = parseInt(checkbox.value);
        selectedPersonIds.add(personId);
        item.classList.add('selected');
        checkbox.checked = true;
    });
}

/**
 * Deselect all persons
 */
function selectNoPersons() {
    document.querySelectorAll('.person-select-item').forEach(item => {
        const checkbox = item.querySelector('input[type="checkbox"]');
        const personId = parseInt(checkbox.value);
        selectedPersonIds.delete(personId);
        item.classList.remove('selected');
        checkbox.checked = false;
    });
}

/**
 * Trigger file picker for adding reference
 */
function triggerAddReference(personId) {
    document.getElementById(`ref-input-${personId}`).click();
}

/**
 * Add multiple reference images to an existing person
 */
async function addMultipleReferences(personId, inputElement) {
    const files = inputElement.files;
    if (!files || files.length === 0) return;
    
    const totalFiles = files.length;
    let successCount = 0;
    let failCount = 0;
    let errors = [];
    
    // Show progress
    const originalText = event.target?.textContent;
    
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const formData = new FormData();
        formData.append('reference_image', file);
        
        try {
            const response = await fetch(`/api/operator/persons/${personId}/add-reference`, {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (response.ok) {
                successCount++;
            } else {
                failCount++;
                errors.push(`${file.name}: ${result.detail || 'Failed'}`);
            }
        } catch (error) {
            failCount++;
            errors.push(`${file.name}: Network error`);
            console.error('Error adding reference:', error);
        }
    }
    
    // Show summary
    let message = `Added ${successCount} of ${totalFiles} reference(s).`;
    if (failCount > 0) {
        message += `\n\nFailed (${failCount}):\n${errors.join('\n')}`;
    }
    alert(message);
    
    // Refresh to show updated count
    loadPersons();
    
    // Clear the input for next use
    inputElement.value = '';
}

/**
 * Delete a person from the registry
 */
async function deletePerson(personId, personName) {
    if (!confirm(`Are you sure you want to delete "${personName}"?\n\nThis will remove them from the registry but NOT delete any already sorted photos.`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/operator/persons/${personId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            loadPersons();
            loadPersonSelection();  // Refresh selection list too
            selectedPersonIds.delete(personId);  // Remove from selection
            loadJobStatus(); // Update job status (may affect can_start)
        } else {
            const error = await response.json();
            alert(error.detail || 'Failed to delete person');
        }
    } catch (error) {
        alert('Network error. Please try again.');
        console.error('Error deleting person:', error);
    }
}

/**
 * Load existing job configuration
 */
async function loadJobConfig() {
    try {
        const response = await fetch('/api/operator/job-config');
        const data = await response.json();
        
        if (data.source_root) {
            document.getElementById('source-root').value = data.source_root;
        }
        if (data.output_root) {
            document.getElementById('output-root').value = data.output_root;
        }
        
        // Load selected persons
        if (data.selected_person_ids && data.selected_person_ids.length > 0) {
            selectedPersonIds = new Set(data.selected_person_ids);
            // Update checkboxes after a short delay (let person selection load first)
            setTimeout(() => {
                data.selected_person_ids.forEach(id => {
                    const checkbox = document.getElementById(`select-person-${id}`);
                    if (checkbox) {
                        checkbox.checked = true;
                        checkbox.closest('.person-select-item')?.classList.add('selected');
                    }
                });
            }, 500);
        }
    } catch (error) {
        console.error('Error loading job config:', error);
    }
}

/**
 * Check if worker is running
 */
async function checkWorkerStatus() {
    const statusDiv = document.getElementById('worker-status');
    
    try {
        const response = await fetch('/api/tracker/worker-status');
        const data = await response.json();
        
        if (data.online) {
            const statusText = formatWorkerStatus(data.status);
            statusDiv.innerHTML = `
                <div class="status-indicator online">
                    <span class="dot"></span>
                    <span class="text">Worker Online</span>
                </div>
                <p class="worker-hint">Status: ${statusText}</p>
                <p class="worker-hint" style="font-size: 0.75rem; color: var(--text-muted);">PID: ${data.pid || 'unknown'}</p>
            `;
        } else {
            statusDiv.innerHTML = `
                <div class="status-indicator offline">
                    <span class="dot"></span>
                    <span class="text">Worker Offline</span>
                </div>
                <p class="worker-hint">Start the worker with: <code>python scripts/run_worker.py</code></p>
            `;
        }
    } catch (error) {
        // Worker status endpoint might not be available
        console.error('Error checking worker status:', error);
    }
}

/**
 * Format worker status for display
 */
function formatWorkerStatus(status) {
    if (!status) return 'Unknown';
    
    const statusMap = {
        'starting': 'Starting up...',
        'resuming': 'Resuming interrupted batches...',
        'idle': 'Idle - ready',
        'waiting_for_config': 'Waiting for job configuration',
        'waiting_for_start': 'Waiting for Start command',
        'discovering_images': 'Discovering images...',
        'completed': 'All batches completed!',
    };
    
    if (statusMap[status]) {
        return statusMap[status];
    }
    
    if (status.startsWith('processing_batch_')) {
        const batchId = status.replace('processing_batch_', '');
        return `Processing batch #${batchId}`;
    }
    
    if (status.startsWith('error:')) {
        return `Error: ${status.replace('error: ', '')}`;
    }
    
    return status;
}

// ============================================================================
// Job Control
// ============================================================================

/**
 * Load and display job status
 */
async function loadJobStatus() {
    const display = document.getElementById('job-status-display');
    const startBtn = document.getElementById('btn-start-job');
    const stopBtn = document.getElementById('btn-stop-job');
    
    try {
        const response = await fetch('/api/operator/job-status');
        const data = await response.json();
        
        // Update display
        const statusColor = getStatusColor(data.status);
        display.innerHTML = `
            <div class="status-text" style="color: ${statusColor};">
                Job Status: <strong>${data.status.toUpperCase()}</strong>
            </div>
            <span class="status-message">${data.message}</span>
        `;
        
        // Update buttons
        startBtn.disabled = !data.can_start;
        stopBtn.disabled = data.status !== 'running';
        
    } catch (error) {
        display.innerHTML = '<p class="loading">Error loading status</p>';
        console.error('Error loading job status:', error);
    }
}

/**
 * Get color for job status
 */
function getStatusColor(status) {
    const colors = {
        'configured': 'var(--text-secondary)',
        'ready': 'var(--accent-cyan)',
        'running': 'var(--accent-green)',
        'stopped': 'var(--accent-yellow)',
        'completed': 'var(--accent-green)',
    };
    return colors[status] || 'var(--text-primary)';
}

/**
 * Start the processing job
 */
async function startJob() {
    const startBtn = document.getElementById('btn-start-job');
    startBtn.disabled = true;
    startBtn.textContent = 'Starting...';
    
    try {
        const response = await fetch('/api/operator/start-job', {
            method: 'POST'
        });
        
        if (response.ok) {
            loadJobStatus();
        } else {
            const error = await response.json();
            alert(error.detail || 'Failed to start job');
        }
    } catch (error) {
        alert('Network error. Please try again.');
        console.error('Error starting job:', error);
    } finally {
        startBtn.textContent = '▶ Start Job';
        loadJobStatus();
    }
}

/**
 * Stop the processing job
 */
async function stopJob() {
    if (!confirm('Are you sure you want to stop the job?\n\nThe current batch will complete before stopping.')) {
        return;
    }
    
    const stopBtn = document.getElementById('btn-stop-job');
    stopBtn.disabled = true;
    stopBtn.textContent = 'Stopping...';
    
    try {
        const response = await fetch('/api/operator/stop-job', {
            method: 'POST'
        });
        
        if (response.ok) {
            loadJobStatus();
        } else {
            const error = await response.json();
            alert(error.detail || 'Failed to stop job');
        }
    } catch (error) {
        alert('Network error. Please try again.');
        console.error('Error stopping job:', error);
    } finally {
        stopBtn.textContent = '⏹ Stop Job';
        loadJobStatus();
    }
}

/**
 * Setup job configuration form handler
 */
function setupJobConfigForm() {
    const form = document.getElementById('job-config-form');
    const status = document.getElementById('job-config-status');
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = new FormData(form);
        
        // Get selected person IDs (empty array means all persons)
        const selectedIds = Array.from(selectedPersonIds);
        
        const data = {
            source_root: formData.get('source_root'),
            output_root: formData.get('output_root'),
            selected_person_ids: selectedIds.length > 0 ? selectedIds : null
        };
        
        try {
            const response = await fetch('/api/operator/job-config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            
            if (response.ok) {
                const personCount = selectedIds.length > 0 ? selectedIds.length : 'all';
                showStatus(status, 'success', `Configuration saved! Searching for ${personCount} person(s).`);
            } else {
                showStatus(status, 'error', result.detail || 'Error saving configuration');
            }
        } catch (error) {
            showStatus(status, 'error', 'Network error. Please try again.');
            console.error('Error saving job config:', error);
        }
    });
}

/**
 * Setup person seeding form handler
 * Supports multiple reference images when creating a new person
 */
function setupSeedPersonForm() {
    const form = document.getElementById('seed-person-form');
    const status = document.getElementById('seed-person-status');
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const submitBtn = form.querySelector('button[type="submit"]');
        const fileInput = document.getElementById('reference-image');
        const files = fileInput.files;
        
        if (!files || files.length === 0) {
            showStatus(status, 'error', 'Please select at least one reference image');
            return;
        }
        
        const name = form.querySelector('[name="name"]').value;
        const folderName = form.querySelector('[name="folder_name"]').value;
        
        submitBtn.disabled = true;
        submitBtn.textContent = `Processing 1/${files.length}...`;
        
        try {
            // Step 1: Create person with first image
            const firstFormData = new FormData();
            firstFormData.append('name', name);
            firstFormData.append('folder_name', folderName);
            firstFormData.append('reference_image', files[0]);
            
            const response = await fetch('/api/operator/seed-person', {
                method: 'POST',
                body: firstFormData
            });
            
            const result = await response.json();
            
            if (!response.ok) {
                showStatus(status, 'error', result.detail || 'Error creating person');
                return;
            }
            
            const personId = result.person_id;
            let successCount = 1;
            let failCount = 0;
            let errors = [];
            
            // Step 2: Add remaining images as additional references
            for (let i = 1; i < files.length; i++) {
                submitBtn.textContent = `Processing ${i + 1}/${files.length}...`;
                
                const refFormData = new FormData();
                refFormData.append('reference_image', files[i]);
                
                try {
                    const refResponse = await fetch(`/api/operator/persons/${personId}/add-reference`, {
                        method: 'POST',
                        body: refFormData
                    });
                    
                    const refResult = await refResponse.json();
                    
                    if (refResponse.ok) {
                        successCount++;
                    } else {
                        failCount++;
                        errors.push(`${files[i].name}: ${refResult.detail || 'Failed'}`);
                    }
                } catch (err) {
                    failCount++;
                    errors.push(`${files[i].name}: Network error`);
                }
            }
            
            // Show summary
            let message = `Person "${name}" created with ${successCount} reference(s).`;
            if (failCount > 0) {
                message += `\n${failCount} failed: ${errors.join(', ')}`;
            }
            showStatus(status, 'success', message);
            form.reset();
            loadPersons();
            loadPersonSelection();  // Refresh selection list
            
        } catch (error) {
            showStatus(status, 'error', 'Network error. Please try again.');
            console.error('Error seeding person:', error);
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Add Person';
        }
    });
}

/**
 * Show status message
 */
function showStatus(element, type, message) {
    element.className = `status-message ${type}`;
    element.textContent = message;
    
    // Auto-hide success messages after 5 seconds
    if (type === 'success') {
        setTimeout(() => {
            element.className = 'status-message';
        }, 5000);
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================================
// Folder Browser
// ============================================================================

let folderBrowserState = {
    targetInputId: null,
    currentPath: '',
    parentPath: null
};

/**
 * Open the folder browser modal
 */
function openFolderBrowser(inputId) {
    folderBrowserState.targetInputId = inputId;
    
    // Get current value from input as starting point
    const currentValue = document.getElementById(inputId).value;
    
    // Show modal
    document.getElementById('folder-browser-modal').style.display = 'flex';
    
    // Load folders (start from current value or root)
    if (currentValue && currentValue.trim()) {
        loadFolders(currentValue);
    } else {
        loadFolders(null); // Load drives/root
    }
}

/**
 * Close the folder browser modal
 */
function closeFolderBrowser() {
    document.getElementById('folder-browser-modal').style.display = 'none';
    folderBrowserState.targetInputId = null;
}

/**
 * Load folders from the server
 */
async function loadFolders(path) {
    const listContainer = document.getElementById('folder-list');
    const pathDisplay = document.getElementById('current-path');
    const parentBtn = document.getElementById('btn-parent');
    
    listContainer.innerHTML = '<p class="loading">Loading...</p>';
    
    try {
        const url = path ? `/api/operator/browse-folders?path=${encodeURIComponent(path)}` : '/api/operator/browse-folders';
        const response = await fetch(url);
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to load folders');
        }
        
        const data = await response.json();
        
        // Update state
        folderBrowserState.currentPath = data.current_path;
        folderBrowserState.parentPath = data.parent_path;
        
        // Update UI
        pathDisplay.textContent = data.current_path || 'Select a drive';
        parentBtn.disabled = !data.parent_path && data.current_path !== '';
        
        // Render folder list
        if (data.folders.length === 0) {
            listContainer.innerHTML = '<p class="loading">No subfolders</p>';
        } else {
            listContainer.innerHTML = data.folders.map(folder => `
                <div class="folder-item ${folder.is_drive ? 'drive' : ''}" 
                     onclick="navigateToFolder('${escapeHtml(folder.path.replace(/\\/g, '\\\\'))}')">
                    <span class="folder-icon">${folder.is_drive ? '💾' : '📁'}</span>
                    <span class="folder-name">${escapeHtml(folder.name)}</span>
                </div>
            `).join('');
        }
        
    } catch (error) {
        listContainer.innerHTML = `<p class="loading" style="color: var(--accent-red);">Error: ${escapeHtml(error.message)}</p>`;
        console.error('Error loading folders:', error);
    }
}

/**
 * Navigate to a specific folder
 */
function navigateToFolder(path) {
    loadFolders(path);
}

/**
 * Navigate to parent folder
 */
function navigateToParent() {
    if (folderBrowserState.parentPath !== null) {
        loadFolders(folderBrowserState.parentPath);
    } else if (folderBrowserState.currentPath) {
        // Go back to drive list
        loadFolders(null);
    }
}

/**
 * Select the current folder and close modal
 */
function selectCurrentFolder() {
    if (folderBrowserState.currentPath && folderBrowserState.targetInputId) {
        document.getElementById(folderBrowserState.targetInputId).value = folderBrowserState.currentPath;
    }
    closeFolderBrowser();
}

// Close modal when clicking outside
document.addEventListener('click', (e) => {
    const modal = document.getElementById('folder-browser-modal');
    if (e.target === modal) {
        closeFolderBrowser();
    }
});

// Close modal with Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeFolderBrowser();
    }
});

