/**
 * Operator Panel JavaScript
 * Handles job configuration, person seeding, and job control
 */

// Global state for selected persons
let selectedPersonIds = new Set();
let groupModeEnabled = false;  // NEW: Group mode state
let lastJobStatus = ''; // Track status for animations
let allPersons = []; // Global store for registry data

const THEME_KEY = 'face_segregation_theme';

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    loadPersons();
    loadJobConfig();
    loadJobStatus();
    loadProgress();
    loadRegistryCard();
    checkWorkerStatus();
    setInterval(checkWorkerStatus, 3000);
    setInterval(refreshJobAndProgress, 1000);
    setupJobConfigForm();
    setupSeedPersonForm();
    
    // Add global button press handlers
    document.addEventListener('mousedown', (e) => {
        const btn = e.target.closest('.btn');
        if (btn && window.Animations) {
            Animations.buttonPress(btn);
        }
    });

    lucide.createIcons();
});

function initTheme() {
    const savedTheme = localStorage.getItem(THEME_KEY);
    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    const checkbox = document.getElementById('theme-checkbox');
    
    if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
        document.documentElement.setAttribute('data-theme', 'dark');
        if (checkbox) checkbox.checked = true;
    } else {
        if (checkbox) checkbox.checked = false;
    }
}

function toggleTheme() {
    const checkbox = document.getElementById('theme-checkbox');
    const isDark = checkbox.checked;

    if (isDark) {
        document.documentElement.setAttribute('data-theme', 'dark');
        localStorage.setItem(THEME_KEY, 'dark');
    } else {
        document.documentElement.removeAttribute('data-theme');
        localStorage.setItem(THEME_KEY, 'light');
    }
}

/**
 * Load and display registered persons (into #persons-list in Person Registry modal)
 */
async function loadPersons() {
    const container = document.getElementById('persons-list');
    if (!container) return;
    try {
        const response = await fetch('/api/operator/persons');
        const data = await response.json();
        if (data.persons && data.persons.length > 0) {
            container.innerHTML = data.persons.map(person => `
                <div class="person-card person-card-compact" data-person-id="${person.person_id}" data-person-name="${escapeHtml(person.name)}" data-folder="${escapeHtml(person.output_folder_rel)}" data-embedding-count="${person.embedding_count}" onclick="openPersonDetailsModal(this)" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();openPersonDetailsModal(this);}" role="button" tabindex="0">
                    <div class="person-avatar">
                        <img src="/api/operator/persons/${person.person_id}/thumbnail" 
                             alt="${escapeHtml(person.name)}"
                             onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                        <div class="avatar-placeholder" style="display:none;"><i data-lucide="user" class="icon icon-lg"></i></div>
                    </div>
                    <div class="name">${escapeHtml(person.name)}</div>
                </div>
            `).join('');
            lucide.createIcons();
            
            // Animate cards
            if (window.Animations) {
                Animations.cards(container.querySelectorAll('.person-card'));
            }
        } else {
            container.innerHTML = '<p class="loading">No persons registered yet</p>';
        }
    } catch (error) {
        container.innerHTML = '<p class="loading">Error loading persons</p>';
        console.error('Error loading persons:', error);
    }
}

/**
 * Load the registry thumb grid on the Person Registry card: 5 person thumbnails + 1 add circle.
 * Layout: row 1 = 3 persons, row 2 = 2 persons + add circle.
 */
async function loadRegistryCard() {
    const grid = document.getElementById('registry-thumb-grid');
    const badge = document.getElementById('registry-count-badge');
    if (!grid) return;
    
    try {
        const response = await fetch('/api/operator/persons');
        const data = await response.json();
        allPersons = data.persons || [];
        
        // Update Count Badge
        if (badge) {
            badge.textContent = `${allPersons.length} People`;
        }

        renderRegistryGrid(allPersons);
    } catch (error) {
        console.error('Error loading registry card:', error);
    }
}

/**
 * Render thumbnails to the registry grid
 */
function renderRegistryGrid(persons) {
    const grid = document.getElementById('registry-thumb-grid');
    if (!grid) return;

    if (persons.length === 0) {
        grid.innerHTML = '<div class="registry-empty-state">No people found</div>';
        return;
    }

    const cells = persons.map(p => `
        <div class="registry-thumb-cell" title="${p.name}">
            <img src="/api/operator/persons/${p.person_id}/thumbnail" alt="${p.name}" 
                 onerror="this.parentElement.classList.add('placeholder'); this.innerHTML='<i data-lucide=\\'user\\' class=\\'icon\\'></i>'; lucide.createIcons();">
        </div>
    `);
    
    grid.innerHTML = cells.join('');
    lucide.createIcons();
    
    // Animate grid cells
    if (window.Animations) {
        Animations.cards(grid.querySelectorAll('.registry-thumb-cell'));
    }
}

/**
 * Filter the registry grid based on search input
 */
function filterRegistry() {
    const query = (document.getElementById('registry-search-input').value || '').toLowerCase();
    const filtered = allPersons.filter(p => {
        const nameMatch = p.name && p.name.toLowerCase().includes(query);
        const idMatch = String(p.person_id).toLowerCase().includes(query);
        return nameMatch || idMatch;
    });
    renderRegistryGrid(filtered);
}

/**
 * Update Job Config card summary from form/state
 */
function updateJobConfigCard() {
    var srcEl = document.getElementById('job-config-source');
    var outEl = document.getElementById('job-config-output');
    if (!srcEl || !outEl) return;
    var srcInp = document.getElementById('source-root');
    var outInp = document.getElementById('output-root');
    srcEl.textContent = (srcInp && srcInp.value) ? (srcInp.value.length > 50 ? srcInp.value.slice(0, 47) + '...' : srcInp.value) : '—';
    outEl.textContent = (outInp && outInp.value) ? (outInp.value.length > 50 ? outInp.value.slice(0, 47) + '...' : outInp.value) : '—';
}

/**
 * Load person selection list (modal) and compact summary
 */
async function loadPersonSelection() {
    const container = document.getElementById('person-selection-list');
    const summaryEl = document.getElementById('person-selection-summary');
    try {
        const response = await fetch('/api/operator/persons');
        const data = await response.json();
        const persons = data.persons || [];
        if (container) {
            if (persons.length > 0) {
                container.innerHTML = persons.map(person => `
                    <div class="person-select-item ${selectedPersonIds.has(person.person_id) ? 'selected' : ''}"
                         data-person-id="${person.person_id}" role="button" tabindex="0"
                         onclick="togglePersonSelection(${person.person_id}, this)"
                         onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();togglePersonSelection(${person.person_id}, this);}">
                        <img src="/api/operator/persons/${person.person_id}/thumbnail" class="thumb" alt=""
                             onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                        <span class="thumb-placeholder" style="display:none;"><i data-lucide="user" class="icon icon-sm"></i></span>
                        <span class="select-name">${escapeHtml(person.name)}</span>
                    </div>
                `).join('');
                lucide.createIcons();
            } else {
                container.innerHTML = '<p class="loading">No persons registered. Add persons first.</p>';
            }
        }
        if (summaryEl) {
            var M = persons.length;
            var N = selectedPersonIds.size;
            if (M === 0) summaryEl.textContent = 'No persons';
            else if (N === 0) summaryEl.textContent = 'None selected';
            else if (N === M) summaryEl.textContent = 'All selected';
            else summaryEl.textContent = N + ' of ' + M + ' selected';
        }
        
        // Render selected thumbnails in the Search For card
        const thumbContainer = document.getElementById('selected-people-thumbnails');
        if (thumbContainer) {
            const MAX_THUMBS = 5;
            const selectedPersons = persons.filter(p => selectedPersonIds.has(p.person_id));
            
            if (selectedPersons.length === 0) {
                thumbContainer.innerHTML = '';
            } else {
                const thumbs = selectedPersons.slice(0, MAX_THUMBS).map(p => 
                    `<img src="/api/operator/persons/${p.person_id}/thumbnail" 
                          alt="${escapeHtml(p.name)}" 
                          class="thumb-avatar" 
                          title="${escapeHtml(p.name)}"
                          onerror="this.style.display='none';">`
                );
                
                // Add overflow badge if more than MAX_THUMBS
                if (selectedPersons.length > MAX_THUMBS) {
                    thumbs.push(`<span class="thumb-overflow">+${selectedPersons.length - MAX_THUMBS}</span>`);
                }
                
                thumbContainer.innerHTML = thumbs.join('');
            }
        }
    } catch (error) {
        if (container) container.innerHTML = '<p class="loading">Error loading persons</p>';
        if (summaryEl) summaryEl.textContent = '—';
        console.error('Error loading person selection:', error);
    }
}

/**
 * Toggle person selection (click on person card)
 */
function togglePersonSelection(personId, element) {
    if (selectedPersonIds.has(personId)) {
        selectedPersonIds.delete(personId);
        element.classList.remove('selected');
        // Animation: subtle press
        if (window.Animations) {
             anime({
                targets: element,
                scale: [1, 0.95, 1],
                duration: 200,
                easing: 'easeOutQuad'
            });
        }
    } else {
        selectedPersonIds.add(personId);
        element.classList.add('selected');
        // Animation: pop effect
        if (window.Animations) {
            anime({
                targets: element,
                scale: [1, 1.05, 1],
                duration: 300,
                easing: 'easeOutBack'
            });
        }
    }
}

/**
 * Select all persons
 */
function selectAllPersons() {
    document.querySelectorAll('.person-select-item').forEach(item => {
        const personId = parseInt(item.getAttribute('data-person-id'), 10);
        if (!isNaN(personId)) {
            selectedPersonIds.add(personId);
            item.classList.add('selected');
        }
    });
}

/**
 * Deselect all persons
 */
function selectNoPersons() {
    document.querySelectorAll('.person-select-item').forEach(item => {
        const personId = parseInt(item.getAttribute('data-person-id'), 10);
        if (!isNaN(personId)) {
            selectedPersonIds.delete(personId);
            item.classList.remove('selected');
        }
    });
}

/**
 * Toggle group mode on/off
 */
function toggleGroupMode() {
    groupModeEnabled = !groupModeEnabled;
    const btn = document.getElementById('btn-group-mode');
    const config = document.getElementById('group-mode-config');
    
    if (groupModeEnabled) {
        btn.classList.add('active');
        btn.innerHTML = '<i data-lucide="users" class="icon icon-sm"></i>Group Mode ON';
        if (config) config.style.display = 'block';
        
        // Animation: highlight the button
        if (window.Animations) {
            anime({
                targets: btn,
                scale: [1, 1.05, 1],
                duration: 300,
                easing: 'easeOutBack'
            });
        }
    } else {
        btn.classList.remove('active');
        btn.innerHTML = '<i data-lucide="users" class="icon icon-sm"></i>Select Group';
        if (config) config.style.display = 'none';
    }
    lucide.createIcons();
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
    
    loadPersons();
    loadRegistryCard();
    inputElement.value = '';
}

/**
 * Delete a person from the registry.
 * @returns {Promise<boolean>} true if deleted, false if cancelled or error
 */
async function deletePerson(personId, personName) {
    if (!confirm(`Are you sure you want to delete "${personName}"?\n\nThis will remove them from the registry but NOT delete any already sorted photos.`)) {
        return false;
    }
    
    try {
        const response = await fetch(`/api/operator/persons/${personId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            selectedPersonIds.delete(personId);
            loadPersons();
            loadPersonSelection();
            loadRegistryCard();
            loadJobStatus();
            return true;
        } else {
            const error = await response.json();
            alert(error.detail || 'Failed to delete person');
            return false;
        }
    } catch (error) {
        alert('Network error. Please try again.');
        console.error('Error deleting person:', error);
        return false;
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
        }
        
        // Load group mode state
        groupModeEnabled = data.group_mode || false;
        const btn = document.getElementById('btn-group-mode');
        const config = document.getElementById('group-mode-config');
        if (groupModeEnabled) {
            if (btn) {
                btn.classList.add('active');
                btn.innerHTML = '<i data-lucide="users" class="icon icon-sm"></i>Group Mode ON';
            }
            if (config) config.style.display = 'block';
            if (data.group_folder_name) {
                const folderInput = document.getElementById('group-folder-name');
                if (folderInput) folderInput.value = data.group_folder_name;
            }
        } else {
            if (btn) btn.classList.remove('active');
            if (config) config.style.display = 'none';
        }
        
        updateJobConfigCard();
        loadPersonSelection();
        lucide.createIcons();
    } catch (error) {
        console.error('Error loading job config:', error);
        loadPersonSelection();
    }
}

/**
 * Check if worker is running
 */
async function checkWorkerStatus() {
    const dot = document.getElementById('worker-dot-v2');
    const text = document.getElementById('worker-text-v2');
    const hint = document.getElementById('worker-hint-v2');
    
    if (!dot || !text) return;

    try {
        const response = await fetch('/api/tracker/worker-status');
        const data = await response.json();
        
        if (data.online) {
            dot.className = 'connection-dot online';
            text.textContent = 'Worker Online';
            const statusText = formatWorkerStatus(data.status);
            if (hint) hint.innerHTML = `Running • ${statusText} • PID ${data.pid || '?'}`;
        } else {
            dot.className = 'connection-dot offline';
            text.textContent = 'Worker Offline';
            if (hint) hint.innerHTML = 'Run <code>python scripts/run_worker.py</code>';
        }
    } catch (error) {
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
 * Refresh job status and progress (called every 1s by setInterval)
 */
function refreshJobAndProgress() {
    loadJobStatus();
    loadProgress();
}

/**
 * Load and display job status
 */
async function loadJobStatus() {
    const actionBtn = document.getElementById('btn-job-action');
    const termBtn = document.getElementById('btn-job-terminate-mini');
    const statusBadge = document.getElementById('job-status-badge');
    const statusLabel = document.getElementById('status-label');
    const statusMsg = document.getElementById('job-status-message-v2');

    if (!actionBtn || !statusBadge) return;
    
    try {
        const r = await fetch('/api/operator/job-status');
        const data = await r.json();
        const status = data.status || 'configured';
        const msg = data.message || 'System ready';
        
        // Trigger animation if status changed
        if (status !== lastJobStatus) {
            if (window.Animations) {
                // Subtle pop for badge change
                anime({
                    targets: statusBadge,
                    scale: [1, 1.1, 1],
                    duration: 400,
                    easing: 'easeOutBack'
                });
                
                // Cross-fade for message
                if (statusMsg) {
                    anime({
                        targets: statusMsg,
                        opacity: [1, 0, 1],
                        translateY: [0, -5, 0],
                        duration: 500,
                        easing: 'easeInOutQuad',
                        update: (anim) => {
                            if (anim.progress > 50 && statusMsg.textContent !== msg) {
                                statusMsg.textContent = msg;
                            }
                        }
                    });
                }
            } else {
                statusMsg.textContent = msg;
            }
            lastJobStatus = status;
        } else {
            // Just update message if it changed within same status
            if (statusMsg && statusMsg.textContent !== msg) {
                statusMsg.textContent = msg;
            }
        }
        
        // Update Badge Class
        statusBadge.className = 'status-badge-apple ' + status;
        statusLabel.textContent = status.toUpperCase();

        // Update Action Button
        if (status === 'running') {
            actionBtn.innerHTML = '<i data-lucide="pause" class="icon icon-sm"></i><span>Stop Job</span>';
            actionBtn.classList.remove('primary');
            actionBtn.classList.add('danger-light'); // Subtle red for stop
        } else if (status === 'terminating') {
            actionBtn.innerHTML = '<i data-lucide="loader-2" class="icon icon-sm spin"></i><span>Stopping...</span>';
            actionBtn.disabled = true;
        } else {
            actionBtn.innerHTML = '<i data-lucide="play" class="icon icon-sm"></i><span>Start Job</span>';
            actionBtn.classList.add('primary');
            actionBtn.classList.remove('danger-light');
            actionBtn.disabled = !data.can_start;
        }
        
        if (termBtn) termBtn.disabled = status !== 'running';
        
        lucide.createIcons();
    } catch (e) {
        console.error('Error loading job status:', e);
    }
}

/**
 * Main action handler for the unified button
 */
function handleJobActionMain() {
    const btn = document.getElementById('btn-job-action');
    const text = btn.textContent.toLowerCase();
    
    if (text.includes('stop')) {
        stopJob();
    } else if (text.includes('start')) {
        startJob();
    }
}

/**
 * Load and display progress (from progress.json via tracker API)
 */
async function loadProgress() {
    var section = document.getElementById('progress-section');
    var initializingEl = document.getElementById('progress-initializing');
    var emptyEl = document.getElementById('progress-empty');
    var sourceLine = document.getElementById('progress-source-line');
    var currentImageEl = document.getElementById('progress-current-image');
    var speedEl = document.getElementById('progress-speed');
    var bar = document.getElementById('progress-bar');
    var text = document.getElementById('progress-text');
    var time = document.getElementById('progress-time');
    if (!section || !bar || !text) return;
    
    try {
        var r = await fetch('/api/tracker/progress');
        var d = await r.json();
        var total = d.total_images || 0;
        var done = d.processed_images || 0;
        var pct = d.completion_percent || 0;
        
        // Check if job is running but no progress yet
        var jobStatusEl = document.getElementById('job-status-display');
        var isRunning = jobStatusEl && jobStatusEl.innerHTML.includes('RUNNING');
        
        if (total > 0) {
            // Hide empty and initializing, show progress
            if (emptyEl) emptyEl.style.display = 'none';
            if (initializingEl) initializingEl.style.display = 'none';
            section.style.display = 'flex';
            
            if (sourceLine) {
                sourceLine.style.display = 'none';
                sourceLine.innerHTML = '';
            }
            
            // Update Stats Dashboard Grid
            var statImagesDone = document.getElementById('stat-images-done');
            var statSpeed = document.getElementById('stat-speed');
            var statPercent = document.getElementById('stat-percent');
            var statElapsed = document.getElementById('stat-elapsed');
            
            if (statImagesDone) statImagesDone.textContent = done.toLocaleString();
            if (statSpeed) statSpeed.textContent = (d.images_per_second || 0).toFixed(2);
            if (statPercent) statPercent.textContent = pct.toFixed(0) + '%';
            if (statElapsed) statElapsed.textContent = d.elapsed_formatted || '—';
            
            // Always set current image text (placeholder if empty) to prevent layout shift
            if (currentImageEl) {
                if (d.current_image && String(d.current_image).trim()) {
                    currentImageEl.textContent = 'Current: ' + escapeHtml(d.current_image);
                } else {
                    currentImageEl.innerHTML = '&nbsp;'; // Reserve space
                }
            }
            
            // Always set speed text (placeholder if no data) to prevent layout shift
            if (speedEl) {
                if (d.images_per_second != null && d.images_per_second > 0) {
                    speedEl.textContent = 'Speed: ' + Number(d.images_per_second).toFixed(2) + ' img/s';
                    updateSpeedGraph(d.images_per_second);
                } else {
                    speedEl.innerHTML = '&nbsp;'; // Reserve space
                }
            }
            
            // Update speed graph even if speedEl is hidden
            if (d.images_per_second != null && d.images_per_second > 0) {
                updateSpeedGraph(d.images_per_second);
            }
            
            bar.style.width = pct + '%';
            text.textContent = done.toLocaleString() + ' / ' + total.toLocaleString();
            if (d.current_batch_state) {
                text.textContent += ' — ' + d.current_batch_state;
            }
            var t = '';
            if (d.elapsed_formatted) t += 'Elapsed: ' + d.elapsed_formatted;
            if (d.estimated_remaining_formatted) t += (t ? ' | ' : '') + 'ETC: ~' + d.estimated_remaining_formatted;
            if (time) time.textContent = t || '—';
        } else if (isRunning) {
            // Job is running but no images discovered yet - show initializing
            if (emptyEl) emptyEl.style.display = 'none';
            section.style.display = 'none';
            if (initializingEl) initializingEl.style.display = 'flex';
        } else {
            // No job running and no progress
            section.style.display = 'none';
            if (initializingEl) initializingEl.style.display = 'none';
            if (emptyEl) emptyEl.style.display = 'block';
        }
    } catch (e) {
        section.style.display = 'none';
        if (initializingEl) initializingEl.style.display = 'none';
    }
}

/**
 * Get color for job status
 */
function getStatusColor(status) {
    var colors = {
        'configured': 'var(--text-secondary)',
        'ready': 'var(--accent-cyan)',
        'running': 'var(--accent-green)',
        'terminating': 'var(--accent-yellow)',
        'stopped': 'var(--accent-yellow)',
        'completed': 'var(--accent-green)',
    };
    return colors[status] || 'var(--text-primary)';
}

/**
 * Start the processing job
 */
async function startJob() {
    const actionBtn = document.getElementById('btn-job-action');
    if (actionBtn) {
        actionBtn.disabled = true;
        actionBtn.innerHTML = '<i data-lucide="loader-2" class="icon icon-sm spin"></i><span>Starting...</span>';
        lucide.createIcons();
    }
    
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
        loadJobStatus();
    }
}

/**
 * Stop the processing job (current batch finishes, including writes, then stops)
 */
async function stopJob() {
    if (!confirm('Stop the job? The current batch will complete (including writes to output), then the job will stop.')) return;
    const actionBtn = document.getElementById('btn-job-action');
    if (actionBtn) {
        actionBtn.disabled = true;
        actionBtn.innerHTML = '<i data-lucide="loader-2" class="icon icon-sm spin"></i><span>Stopping...</span>';
        lucide.createIcons();
    }
    try {
        var r = await fetch('/api/operator/stop-job', { method: 'POST' });
        if (r.ok) loadJobStatus(); else { var e = await r.json(); alert(e.detail || 'Failed to stop job'); }
    } catch (err) { alert('Network error.'); console.error(err); }
    finally { 
        loadJobStatus(); 
    }
}

/**
 * Terminate: no new photos analysed; only in-flight writes to output will finish, then stop.
 */
async function terminateJob() {
    if (!confirm('Terminate the job?\n\nNo new photos will be matched or analysed. Only images currently being written to their output folders will be finished, then the job stops.')) return;
    const termBtn = document.getElementById('btn-job-terminate-mini');
    if (termBtn) {
        termBtn.disabled = true;
    }
    try {
        var r = await fetch('/api/operator/terminate-job', { method: 'POST' });
        if (r.ok) loadJobStatus(); else { var e = await r.json(); alert(e.detail || 'Failed to terminate'); }
    } catch (err) { alert('Network error.'); console.error(err); }
    finally { 
        loadJobStatus(); 
    }
}

/**
 * Setup job configuration form handler (form is in job-config modal)
 */
function setupJobConfigForm() {
    const form = document.getElementById('job-config-form');
    const status = document.getElementById('job-config-status');
    const cardStatus = document.getElementById('job-config-card-status');
    if (!form) return;
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(form);
        const selectedIds = Array.from(selectedPersonIds);
        const data = {
            source_root: formData.get('source_root'),
            output_root: formData.get('output_root'),
            selected_person_ids: selectedIds.length > 0 ? selectedIds : null,
            selected_image_paths: null
        };
        try {
            const response = await fetch('/api/operator/job-config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const result = await response.json();
            if (response.ok) {
                updateJobConfigCard();
                var msg = 'Configuration saved! Searching for ' + (selectedIds.length > 0 ? selectedIds.length : 'all') + ' person(s).';
                showStatus(cardStatus || status, 'success', msg);
                closeJobConfigModal();
            } else {
                showStatus(status, 'error', result.detail || 'Error saving configuration');
            }
        } catch (error) {
            showStatus(status, 'error', 'Network error. Please try again.');
            console.error('Error saving job config:', error);
        }
    });
}

// ============================================================================
// Speed Graph Visualization
// ============================================================================

let speedHistory = [];
const MAX_HISTORY = 60; // 1 minute window at 1s polling

function updateSpeedGraph(speed) {
    const container = document.getElementById('speed-graph-container');
    if (!container) return;
    
    // Show container if it was hidden
    if (container.style.display === 'none') {
        container.style.display = 'block';
    }
    
    // Update history
    speedHistory.push(speed);
    if (speedHistory.length > MAX_HISTORY) {
        speedHistory.shift();
    }
    
    if (speedHistory.length < 2) return;

    const width = 300; // SVG viewBox width
    const height = 60; // SVG viewBox height
    
    // Use adaptive scaling - ensures variations are visible even at low speeds
    const actualMax = Math.max(...speedHistory);
    const actualMin = Math.min(...speedHistory);
    const range = actualMax - actualMin;
    
    // Dynamic max: at least 0.2 to avoid jitter, otherwise 20% above the max value
    const scaleMax = Math.max(actualMax * 1.2, 0.2);
    
    // Generate coordinate points
    const points = speedHistory.map((val, idx) => {
        // Map index to 0..width based on MAX_HISTORY capacity
        const x = (idx / (MAX_HISTORY - 1)) * width; 
        
        // Normalize value based on dynamic scale
        const normalizedVal = val / scaleMax;
        
        // Map to height..0 (inverted Y), with small padding
        const padding = 2; // Reduced padding for more vertical space
        const y = height - padding - (normalizedVal * (height - 2 * padding));
        return [x, Math.max(padding, Math.min(height - padding, y))];
    });
    
    // Create smooth curve using cardinal spline approximation
    const lineD = "M " + points.map(p => `${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" L ");
    
    // Create Area Path (Line + fill to bottom)
    const lastPoint = points[points.length - 1];
    const firstPoint = points[0];
    const areaD = lineD + ` L ${lastPoint[0].toFixed(1)} ${height} L ${firstPoint[0].toFixed(1)} ${height} Z`;
    
    // Update DOM
    const areaPath = document.getElementById('speed-graph-area');
    const linePath = document.getElementById('speed-graph-line');
    
    if (areaPath) areaPath.setAttribute('d', areaD);
    if (linePath) linePath.setAttribute('d', lineD);
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
            loadPersonSelection();
            loadRegistryCard();
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
    
    // Animate
    if (window.Animations) {
        Animations.statusMessage(element, type);
    }
    
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
// Modals: Job Config, Person Selection, Person Registry
// ============================================================================

function openJobConfigModal() {
    Animations.modalOpen(document.getElementById('job-config-modal'));
}
function closeJobConfigModal() {
    Animations.modalClose(document.getElementById('job-config-modal'));
}

function openPersonSelectionModal() {
    loadPersonSelection();
    Animations.modalOpen(document.getElementById('person-selection-modal'));
}
function closePersonSelectionModal() {
    Animations.modalClose(document.getElementById('person-selection-modal'));
}

async function applyPersonSelection() {
    try {
        var selectedIds = Array.from(selectedPersonIds);
        
        // Validate group mode requirements
        if (groupModeEnabled) {
            if (selectedIds.length < 2) {
                alert('Group mode requires at least 2 people selected.');
                return;
            }
            var folderName = (document.getElementById('group-folder-name')?.value || '').trim();
            if (!folderName) {
                alert('Please enter a folder name for group mode.');
                document.getElementById('group-folder-name')?.focus();
                return;
            }
        }
        
        var r = await fetch('/api/operator/job-config');
        var data = await r.json();
        var payload = {
            source_root: data.source_root || '',
            output_root: data.output_root || '',
            selected_person_ids: selectedIds.length > 0 ? selectedIds : null,
            selected_image_paths: null,
            group_mode: groupModeEnabled,
            group_folder_name: groupModeEnabled ? document.getElementById('group-folder-name')?.value?.trim() : null
        };
        var res = await fetch('/api/operator/job-config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            closePersonSelectionModal();
            loadPersonSelection();
            loadJobStatus();
            
            // Show success message based on mode
            var msg = groupModeEnabled 
                ? 'Group mode enabled. Photos with ALL ' + selectedIds.length + ' people → ' + payload.group_folder_name
                : 'Searching for ' + (selectedIds.length > 0 ? selectedIds.length : 'all') + ' person(s).';
            console.log(msg);
        } else {
            var e = await res.json();
            alert(e.detail || 'Failed to save selection');
        }
    } catch (err) {
        alert('Network error. Please try again.');
        console.error(err);
    }
}

function openPersonRegistryModal(tab) {
    Animations.modalOpen(document.getElementById('person-registry-modal'));
    switchPersonRegistryTab(tab || 'add');
}
function closePersonRegistryModal() {
    Animations.modalClose(document.getElementById('person-registry-modal'));
}

/**
 * Open Person Details modal from a compact person card (data-person-id, data-person-name, data-folder, data-embedding-count).
 */
function openPersonDetailsModal(cardEl) {
    const modal = document.getElementById('person-details-modal');
    if (!modal) return;
    const id = cardEl.dataset.personId;
    const name = cardEl.dataset.personName || '—';
    const folder = cardEl.dataset.folder || '—';
    const count = cardEl.dataset.embeddingCount != null ? cardEl.dataset.embeddingCount : '0';
    modal.dataset.personId = id;
    modal.dataset.personName = name;
    document.getElementById('person-details-name').textContent = name;
    document.getElementById('person-details-folder').innerHTML = '<i data-lucide="folder" class="icon icon-sm"></i> ' + (folder || '—');
    document.getElementById('person-details-embeddings').innerHTML = '<i data-lucide="image" class="icon icon-sm"></i> ' + count + ' reference(s)';
    lucide.createIcons();
    const refInput = document.getElementById('person-details-ref-input');
    if (refInput) refInput.value = '';
    Animations.modalOpen(modal);
}

function closePersonDetailsModal() {
    const modal = document.getElementById('person-details-modal');
    if (modal) Animations.modalClose(modal);
}

/**
 * Handle "Add more references" in Person Details modal. Reads personId from modal dataset.
 */
async function onPersonDetailsAddRef(inputEl) {
    const modal = document.getElementById('person-details-modal');
    if (!modal) return;
    const pid = modal.dataset.personId ? parseInt(modal.dataset.personId, 10) : null;
    if (!pid) return;
    await addMultipleReferences(pid, inputEl);
    try {
        const r = await fetch('/api/operator/persons');
        const d = await r.json();
        const p = (d.persons || []).find(x => x.person_id === pid);
        const el = document.getElementById('person-details-embeddings');
        if (p && el) {
            el.innerHTML = '<i data-lucide="image" class="icon icon-sm"></i> ' + p.embedding_count + ' reference(s)';
            lucide.createIcons();
        }
    } catch (e) { /* ignore */ }
}

/**
 * Delete person from Person Details modal and close it on success.
 */
async function deletePersonFromDetailsFromModal() {
    const modal = document.getElementById('person-details-modal');
    if (!modal) return;
    const pid = modal.dataset.personId ? parseInt(modal.dataset.personId, 10) : null;
    const name = modal.dataset.personName || '';
    if (!pid) return;
    const deleted = await deletePerson(pid, name);
    if (deleted) closePersonDetailsModal();
}

function switchPersonRegistryTab(tab) {
    document.querySelectorAll('.modal-tab').forEach(function(btn) {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });
    document.querySelectorAll('.modal-tab-pane').forEach(function(pane) {
        var isActive = pane.id === 'person-registry-tab-' + tab;
        pane.classList.toggle('active', isActive);
        // Display is now handled by CSS class .active for animation support
        if (!isActive) pane.style.display = ''; // Clear inline styles
    });
    
    // Show/hide specific footer buttons based on tab
    const submitBtn = document.getElementById('btn-submit-seed');
    if (submitBtn) {
        submitBtn.style.display = (tab === 'add') ? 'inline-flex' : 'none';
    }

    if (tab === 'list') loadPersons();
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
    Animations.modalOpen(document.getElementById('folder-browser-modal'));
    
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
    Animations.modalClose(document.getElementById('folder-browser-modal'));
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
                    <span class="folder-icon"><i data-lucide="${folder.is_drive ? 'hard-drive' : 'folder'}" class="icon icon-sm"></i></span>
                    <span class="folder-name">${escapeHtml(folder.name)}</span>
                </div>
            `).join('');
            lucide.createIcons();
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
        var inp = document.getElementById(folderBrowserState.targetInputId);
        if (inp) inp.value = folderBrowserState.currentPath;
    }
    closeFolderBrowser();
}

// Close modals when clicking overlay or pressing Escape
document.addEventListener('click', (e) => {
    if (!e.target || !e.target.classList || !e.target.classList.contains('modal')) return;
    if (e.target.id === 'folder-browser-modal') closeFolderBrowser();
    else if (e.target.id === 'job-config-modal') closeJobConfigModal();
    else if (e.target.id === 'person-selection-modal') closePersonSelectionModal();
    else if (e.target.id === 'person-registry-modal') closePersonRegistryModal();
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closePersonRegistryModal();
        closePersonSelectionModal();
        closeJobConfigModal();
        closeFolderBrowser();
    }
});

