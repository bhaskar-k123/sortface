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
        updateTimeTracking(data);
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
    const totalEl = document.getElementById('total-images');
    const processedEl = document.getElementById('processed-images');
    const percentEl = document.getElementById('completion-percent');
    
    // Parse current values for animations
    const total = data.total_images || 0;
    const processed = data.processed_images || 0;
    const percent = data.completion_percent || 0;
    
    // Animate stats
    if (window.Animations) {
        Animations.countUp(totalEl, total);
        Animations.countUp(processedEl, processed);
        Animations.countUp(percentEl, percent, '%'); // Note: countUp handles integer rounding, might want decimal for %
        
        // Special handling for percent text if we want decimals
        // For now using simple text update for percent text to keep decimals, 
        // or we could enhance animateCountUp later. 
        // Actually, let's stick to textContent for percent to preserve ".1" precision
        // unless we update animateCountUp.
        percentEl.textContent = `${percent.toFixed(1)}%`;
        
        Animations.progress(document.getElementById('progress-bar'), percent);
    } else {
        // Fallback
        totalEl.textContent = formatNumber(total);
        processedEl.textContent = formatNumber(processed);
        percentEl.textContent = `${percent.toFixed(1)}%`;
        document.getElementById('progress-bar').style.width = `${percent}%`;
    }
}

/**
 * Update time tracking section
 */
function updateTimeTracking(data) {
    const container = document.getElementById('time-tracking');
    
    if (data.elapsed_formatted || data.estimated_remaining_formatted) {
        container.style.display = 'block';
        
        document.getElementById('elapsed-time').textContent = 
            data.elapsed_formatted || '--';
        document.getElementById('remaining-time').textContent = 
            data.estimated_remaining_formatted ? `~${data.estimated_remaining_formatted}` : '--';
        
        // Calculate speed
        if (data.elapsed_seconds && data.processed_images > 0) {
            const speed = data.processed_images / data.elapsed_seconds;
            document.getElementById('processing-speed').textContent = 
                `${speed.toFixed(2)} img/s`;
        } else {
            document.getElementById('processing-speed').textContent = '--';
        }
    } else {
        container.style.display = 'none';
    }
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
    
    container.innerHTML = batches.map(batch => {
        const batchId = escapeHtml(String(batch.batch_id));
        const range = escapeHtml(batch.image_range);
        const state = escapeHtml(batch.state);
        const stateClass = (batch.state || '').toLowerCase().replace(/[^a-z]/g, '');
        return `
            <div class="batch-history-item">
                <div>
                    <span class="batch-id">Batch #${batchId}</span>
                    <span class="batch-range">${range}</span>
                </div>
                <span class="batch-state ${stateClass}">${state}</span>
            </div>
        `;
    }).join('');
}

/**
 * Escape HTML to prevent XSS in innerHTML usage
 * @param {string} text - Text to escape
 * @returns {string} Escaped HTML
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
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

