/**
 * Operator API Service
 * All API calls for the Operator panel
 */

import { get, post, postForm, del } from './api.js';

// ============================================================================
// Job Configuration
// ============================================================================

/**
 * Get current job configuration
 */
export async function getJobConfig() {
    return get('/operator/job-config');
}

/**
 * Save job configuration
 * @param {object} config - { source_root, output_root, selected_person_ids, selected_image_paths }
 */
export async function saveJobConfig(config) {
    return post('/operator/job-config', config);
}

/**
 * Get job status
 */
export async function getJobStatus() {
    return get('/operator/job-status');
}

/**
 * Start the processing job
 */
export async function startJob() {
    return post('/operator/start-job');
}

/**
 * Stop the processing job (current batch finishes, then stops)
 */
export async function stopJob() {
    return post('/operator/stop-job');
}

/**
 * Terminate job (only in-flight writes finish, then stops)
 */
export async function terminateJob() {
    return post('/operator/terminate-job');
}

// ============================================================================
// Person Registry
// ============================================================================

/**
 * Get all registered persons
 */
export async function getPersons() {
    return get('/operator/persons');
}

/**
 * Create a new person with reference image
 * @param {string} name - Person name
 * @param {string} folderName - Output folder name
 * @param {File} referenceImage - Reference image file
 */
export async function seedPerson(name, folderName, referenceImage) {
    const formData = new FormData();
    formData.append('name', name);
    formData.append('folder_name', folderName);
    formData.append('reference_image', referenceImage);
    return postForm('/operator/seed-person', formData);
}

/**
 * Add additional reference image to existing person
 * @param {number} personId - Person ID
 * @param {File} referenceImage - Reference image file
 */
export async function addReference(personId, referenceImage) {
    const formData = new FormData();
    formData.append('reference_image', referenceImage);
    return postForm(`/operator/persons/${personId}/add-reference`, formData);
}

/**
 * Delete a person from the registry
 * @param {number} personId - Person ID
 */
export async function deletePerson(personId) {
    return del(`/operator/persons/${personId}`);
}

/**
 * Get person thumbnail URL
 * @param {number} personId - Person ID
 */
export function getPersonThumbnailUrl(personId) {
    return `/api/operator/persons/${personId}/thumbnail`;
}

// ============================================================================
// Folder Browser
// ============================================================================

/**
 * Browse folders on the local file system
 * @param {string|null} path - Path to browse, null for drives/root
 */
export async function browseFolders(path = null) {
    const endpoint = path 
        ? `/operator/browse-folders?path=${encodeURIComponent(path)}`
        : '/operator/browse-folders';
    return get(endpoint);
}

/**
 * Get list of images in a folder
 * @param {string} path - Folder path
 * @param {boolean} recursive - Include subfolders
 */
export async function getImagesInFolder(path, recursive = false) {
    const endpoint = `/operator/images-in-folder?path=${encodeURIComponent(path)}&recursive=${recursive}`;
    return get(endpoint);
}
