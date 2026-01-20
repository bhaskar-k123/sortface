/**
 * Utility Helper Functions
 * Shared utilities for the frontend
 */

/**
 * Escape HTML to prevent XSS
 * @param {string} text - Text to escape
 * @returns {string} Escaped HTML
 */
export function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Truncate text with ellipsis
 * @param {string} text - Text to truncate
 * @param {number} maxLength - Maximum length
 * @returns {string} Truncated text
 */
export function truncate(text, maxLength = 50) {
    if (!text) return '';
    return text.length > maxLength ? text.slice(0, maxLength - 3) + '...' : text;
}

/**
 * Format seconds to human-readable time string
 * @param {number} seconds - Seconds to format
 * @returns {string} Formatted time (e.g., "1h 23m 45s")
 */
export function formatTime(seconds) {
    if (!seconds || seconds < 0) return '—';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    let result = '';
    if (hours > 0) result += `${hours}h `;
    if (minutes > 0 || hours > 0) result += `${minutes}m `;
    result += `${secs}s`;
    
    return result.trim();
}

/**
 * Format worker status for display
 * @param {string} status - Raw status string
 * @returns {string} Human-readable status
 */
export function formatWorkerStatus(status) {
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

/**
 * Get color for job status
 * @param {string} status - Job status
 * @returns {string} CSS color variable
 */
export function getStatusColor(status) {
    const colors = {
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
 * Show status message with animation
 * @param {HTMLElement} element - Status element
 * @param {string} type - 'success' or 'error'
 * @param {string} message - Message text
 */
export function showStatus(element, type, message) {
    if (!element) return;
    
    element.className = `status-message ${type}`;
    element.textContent = message;
    
    // Animate if Animations available
    if (window.Animations) {
        window.Animations.statusMessage(element, type);
    }
    
    // Auto-hide success messages after 5 seconds
    if (type === 'success') {
        setTimeout(() => {
            element.className = 'status-message';
        }, 5000);
    }
}

/**
 * Debounce function calls
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in ms
 * @returns {Function} Debounced function
 */
export function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Throttle function calls
 * @param {Function} func - Function to throttle
 * @param {number} limit - Limit time in ms
 * @returns {Function} Throttled function
 */
export function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}
