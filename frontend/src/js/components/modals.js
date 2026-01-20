/**
 * Modal Component
 * Reusable modal handling functions
 */

/**
 * Open a modal with animation
 * @param {string|HTMLElement} modalId - Modal element or ID
 */
export function openModal(modalId) {
    const modal = typeof modalId === 'string' 
        ? document.getElementById(modalId) 
        : modalId;
    
    if (!modal) return;
    
    modal.style.display = 'flex';
    
    // Use Animations if available
    if (window.Animations && window.Animations.modalOpen) {
        window.Animations.modalOpen(modal);
    }
}

/**
 * Close a modal with animation
 * @param {string|HTMLElement} modalId - Modal element or ID
 */
export function closeModal(modalId) {
    const modal = typeof modalId === 'string' 
        ? document.getElementById(modalId) 
        : modalId;
    
    if (!modal) return;
    
    // Use Animations if available
    if (window.Animations && window.Animations.modalClose) {
        window.Animations.modalClose(modal);
    } else {
        modal.style.display = 'none';
    }
}

/**
 * Setup modal close handlers (overlay click and Escape key)
 * @param {string[]} modalIds - Array of modal IDs
 * @param {object} closeCallbacks - Map of modalId to close callback
 */
export function setupModalCloseHandlers(modalIds, closeCallbacks = {}) {
    // Close on overlay click
    document.addEventListener('click', (e) => {
        if (!e.target || !e.target.classList || !e.target.classList.contains('modal')) return;
        
        const modalId = e.target.id;
        if (modalIds.includes(modalId)) {
            if (closeCallbacks[modalId]) {
                closeCallbacks[modalId]();
            } else {
                closeModal(modalId);
            }
        }
    });
    
    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            // Close all open modals
            modalIds.forEach(modalId => {
                const modal = document.getElementById(modalId);
                if (modal && modal.style.display !== 'none') {
                    if (closeCallbacks[modalId]) {
                        closeCallbacks[modalId]();
                    } else {
                        closeModal(modalId);
                    }
                }
            });
        }
    });
}

/**
 * Switch tabs within a modal
 * @param {string} tabName - Tab name to switch to
 * @param {string} tabButtonSelector - Selector for tab buttons
 * @param {string} tabPanePrefix - ID prefix for tab panes
 * @param {Function} onSwitch - Callback when tab switched
 */
export function switchModalTab(tabName, tabButtonSelector, tabPanePrefix, onSwitch = null) {
    // Update tab buttons
    document.querySelectorAll(tabButtonSelector).forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });
    
    // Update tab panes
    document.querySelectorAll(`[id^="${tabPanePrefix}"]`).forEach(pane => {
        const isActive = pane.id === `${tabPanePrefix}${tabName}`;
        pane.classList.toggle('active', isActive);
        pane.style.display = isActive ? 'block' : 'none';
    });
    
    // Callback
    if (onSwitch) {
        onSwitch(tabName);
    }
}
