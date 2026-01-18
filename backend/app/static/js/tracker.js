/**
 * Progress Tracker JavaScript
 * Read-only monitoring - polls state files only
 */

document.addEventListener('DOMContentLoaded', () => {
    // Initial load
    loadProgress();
    
    // Auto-refresh every 2 seconds
    setInterval(loadProgress, 2000);
});

/**
 * Load progress data from state files
 */
async function loadProgress() {
    try {
        const response = await fetch('/api/tracker/progress');
        const data = await response.json();
        
        updateOverallProgress(data);
        updateCurrentBatch(data);
        updateLastCommitted(data);
        updateBatchHistory(data.recent_batches || []);
        
    } catch (error) {
        console.error('Error loading progress:', error);
    }
}

/**
 * Update overall progress section
 */
function updateOverallProgress(data) {
    document.getElementById('total-images').textContent = 
        formatNumber(data.total_images || 0);
    document.getElementById('processed-images').textContent = 
        formatNumber(data.processed_images || 0);
    
    const percent = data.completion_percent || 0;
    document.getElementById('completion-percent').textContent = 
        `${percent.toFixed(1)}%`;
    
    document.getElementById('progress-bar').style.width = `${percent}%`;
}

/**
 * Update current batch section
 */
function updateCurrentBatch(data) {
    document.getElementById('current-superbatch').textContent = 
        data.current_superbatch || '--';
    document.getElementById('current-batch').textContent = 
        data.current_batch_id || '--';
    document.getElementById('image-range').textContent = 
        data.current_image_range || '--';
    
    const stateElement = document.getElementById('batch-state');
    const state = (data.current_batch_state || '--').toLowerCase();
    stateElement.textContent = state.toUpperCase();
    stateElement.className = `info-value batch-state ${state}`;
}

/**
 * Update last committed section
 */
function updateLastCommitted(data) {
    document.getElementById('last-person').textContent = 
        data.last_committed_person || '--';
    document.getElementById('last-image').textContent = 
        data.last_committed_image || '--';
    document.getElementById('last-time').textContent = 
        data.last_committed_time ? formatTime(data.last_committed_time) : '--';
}

/**
 * Update batch history section
 */
function updateBatchHistory(batches) {
    const container = document.getElementById('batch-history');
    
    if (batches.length === 0) {
        container.innerHTML = '<p class="loading">No batches processed yet</p>';
        return;
    }
    
    container.innerHTML = batches.map(batch => `
        <div class="batch-history-item">
            <div>
                <span class="batch-id">Batch #${batch.batch_id}</span>
                <span class="batch-range">${batch.image_range}</span>
            </div>
            <span class="batch-state ${batch.state.toLowerCase()}">${batch.state}</span>
        </div>
    `).join('');
}

/**
 * Format large numbers with commas
 */
function formatNumber(num) {
    return num.toLocaleString();
}

/**
 * Format ISO timestamp to readable time
 */
function formatTime(isoString) {
    try {
        const date = new Date(isoString);
        return date.toLocaleTimeString();
    } catch {
        return isoString;
    }
}

