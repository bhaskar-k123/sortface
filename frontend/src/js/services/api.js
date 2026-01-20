/**
 * Base API Service Layer
 * Centralized fetch configuration and error handling
 */

const API_BASE = '/api';

/**
 * Make an API request with consistent error handling
 * @param {string} endpoint - API endpoint (without base URL)
 * @param {object} options - Fetch options
 * @returns {Promise<object>} Response data
 */
export async function request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    
    const config = {
        ...options,
        headers: {
            ...options.headers,
        }
    };
    
    // Add Content-Type for JSON bodies (but not for FormData)
    if (options.body && !(options.body instanceof FormData)) {
        config.headers['Content-Type'] = 'application/json';
    }
    
    try {
        const response = await fetch(url, config);
        const data = await response.json();
        
        if (!response.ok) {
            throw new ApiError(data.detail || 'API request failed', response.status, data);
        }
        
        return data;
    } catch (error) {
        if (error instanceof ApiError) {
            throw error;
        }
        throw new ApiError('Network error. Please try again.', 0, null);
    }
}

/**
 * Custom API Error class
 */
export class ApiError extends Error {
    constructor(message, status, data) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.data = data;
    }
}

/**
 * GET request helper
 */
export async function get(endpoint) {
    return request(endpoint, { method: 'GET' });
}

/**
 * POST request helper with JSON body
 */
export async function post(endpoint, body = null) {
    const options = { method: 'POST' };
    if (body) {
        options.body = JSON.stringify(body);
    }
    return request(endpoint, options);
}

/**
 * POST request helper with FormData
 */
export async function postForm(endpoint, formData) {
    return request(endpoint, {
        method: 'POST',
        body: formData
    });
}

/**
 * DELETE request helper
 */
export async function del(endpoint) {
    return request(endpoint, { method: 'DELETE' });
}
