/**
 * Tracker API Service
 * All API calls for progress tracking
 */

import { get } from './api.js';

/**
 * Get current progress from state files
 */
export async function getProgress() {
    return get('/tracker/progress');
}

/**
 * Get worker status (online/offline, last heartbeat)
 */
export async function getWorkerStatus() {
    return get('/tracker/worker-status');
}
