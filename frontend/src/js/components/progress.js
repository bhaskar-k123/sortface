/**
 * Progress Component
 * Speed graph visualization and progress display
 */

// Speed history for graph
let speedHistory = [];
const MAX_HISTORY = 60; // 1 minute window at 1s polling

/**
 * Update the speed graph visualization
 * @param {number} speed - Current speed in images/second
 */
export function updateSpeedGraph(speed) {
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
    
    // Dynamic max speed for Y-axis scaling (min 5 to prevent flat lines)
    const maxSpeed = Math.max(Math.max(...speedHistory), 5) * 1.2;
    
    // Generate coordinate points
    const points = speedHistory.map((val, idx) => {
        // Map index to 0..width based on MAX_HISTORY capacity
        const x = (idx / (MAX_HISTORY - 1)) * width; 
        // Map speed to height..0 (inverted Y)
        const y = height - ((val / maxSpeed) * height);
        return [x, y];
    });
    
    // Create Line Path (M x0 y0 L x1 y1 ...)
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
 * Reset the speed graph
 */
export function resetSpeedGraph() {
    speedHistory = [];
    
    const container = document.getElementById('speed-graph-container');
    if (container) {
        container.style.display = 'none';
    }
    
    const areaPath = document.getElementById('speed-graph-area');
    const linePath = document.getElementById('speed-graph-line');
    
    if (areaPath) areaPath.setAttribute('d', '');
    if (linePath) linePath.setAttribute('d', '');
}

/**
 * Update progress bar
 * @param {number} percent - Completion percentage (0-100)
 */
export function updateProgressBar(percent) {
    const bar = document.getElementById('progress-bar');
    if (bar) {
        bar.style.width = `${percent}%`;
    }
}

/**
 * Update progress text
 * @param {string} text - Progress text to display
 */
export function updateProgressText(text) {
    const element = document.getElementById('progress-text');
    if (element) {
        element.textContent = text;
    }
}

/**
 * Update time display
 * @param {string} elapsed - Elapsed time string
 * @param {string} remaining - Estimated remaining time string
 */
export function updateTimeDisplay(elapsed, remaining) {
    const element = document.getElementById('progress-time');
    if (element) {
        let text = '';
        if (elapsed) text += `Elapsed: ${elapsed}`;
        if (remaining) text += (text ? ' | ' : '') + `ETC: ~${remaining}`;
        element.textContent = text || '—';
    }
}
