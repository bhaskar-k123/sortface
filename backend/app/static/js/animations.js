/**
 * Animations Module - Face Photo Segregation System
 * Powered by anime.js
 * 
 * Balanced animations - visible but not distracting
 */

// Check for reduced motion preference
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Animation timing presets (balanced feel)
const TIMING = {
    fast: 200,
    normal: 300,
    slow: 400,
    stagger: 50
};

// Easing presets
const EASE = {
    smooth: 'easeOutQuad',
    bounce: 'easeOutBack',
    snappy: 'easeOutCubic'
};

/**
 * Animate modal open
 * @param {HTMLElement} modal - The modal element
 * @param {Function} onComplete - Callback when animation completes
 */
function animateModalOpen(modal, onComplete) {
    if (prefersReducedMotion) {
        modal.style.display = 'flex';
        if (onComplete) onComplete();
        return;
    }
    
    const content = modal.querySelector('.modal-content');
    modal.classList.add('active'); // Apply visibility: visible and opacity: 1 (base layer)
    modal.style.display = 'flex';
    modal.style.opacity = '0';
    
    if (content) {
        content.style.transform = 'scale(0.9) translateY(20px)';
        content.style.opacity = '0';
    }
    
    // Animate backdrop
    anime({
        targets: modal,
        opacity: [0, 1],
        duration: TIMING.fast,
        easing: 'linear'
    });
    
    // Animate content
    if (content) {
        anime({
            targets: content,
            scale: [0.9, 1],
            translateY: [20, 0],
            opacity: [0, 1],
            duration: TIMING.normal,
            easing: EASE.bounce,
            complete: onComplete
        });
    }
}

/**
 * Animate modal close
 * @param {HTMLElement} modal - The modal element
 * @param {Function} onComplete - Callback when animation completes
 */
function animateModalClose(modal, onComplete) {
    if (prefersReducedMotion) {
        modal.style.display = 'none';
        if (onComplete) onComplete();
        return;
    }
    
    const content = modal.querySelector('.modal-content');
    
    // Animate content out first
    if (content) {
        anime({
            targets: content,
            scale: [1, 0.95],
            translateY: [0, 10],
            opacity: [1, 0],
            duration: TIMING.fast,
            easing: EASE.snappy
        });
    }
    
    // Animate backdrop
    anime({
        targets: modal,
        opacity: [1, 0],
        duration: TIMING.fast,
        easing: 'linear',
        complete: () => {
            modal.style.display = 'none';
            modal.classList.remove('active'); // Reset visibility for next open
            // Reset styles for next open
            modal.style.opacity = '';
            if (content) {
                content.style.transform = '';
                content.style.opacity = '';
            }
            if (onComplete) onComplete();
        }
    });
}

/**
 * Animate page elements on load (staggered entrance)
 * @param {string} selector - CSS selector for elements to animate
 * @param {Object} options - Animation options
 */
function animatePageLoad(selector, options = {}) {
    if (prefersReducedMotion) return;
    
    const elements = document.querySelectorAll(selector);
    if (elements.length === 0) return;
    
    // Set initial state
    elements.forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(15px)';
    });
    
    anime({
        targets: selector,
        opacity: [0, 1],
        translateY: [15, 0],
        duration: options.duration || TIMING.normal,
        delay: anime.stagger(options.stagger || TIMING.stagger),
        easing: EASE.smooth,
        complete: () => {
            // Clean up inline styles
            elements.forEach(el => {
                el.style.opacity = '';
                el.style.transform = '';
            });
        }
    });
}

/**
 * Animate cards with stagger effect
 * @param {string|NodeList} targets - Selector or elements to animate
 */
function animateCards(targets) {
    if (prefersReducedMotion) return;
    
    anime({
        targets: targets,
        scale: [0.9, 1],
        opacity: [0, 1],
        duration: TIMING.normal,
        delay: anime.stagger(TIMING.stagger),
        easing: EASE.bounce
    });
}

/**
 * Animate button press (click feedback)
 * @param {HTMLElement} button - Button element
 */
function animateButtonPress(button) {
    if (prefersReducedMotion) return;
    
    anime({
        targets: button,
        scale: [1, 0.95, 1],
        duration: 150,
        easing: 'easeInOutQuad'
    });
}

/**
 * Animate status message appearance
 * @param {HTMLElement} element - Status message element
 * @param {string} type - 'success' or 'error'
 */
function animateStatusMessage(element, type) {
    if (prefersReducedMotion) return;
    
    if (type === 'error') {
        // Shake for errors
        anime({
            targets: element,
            translateX: [-5, 5, -5, 5, 0],
            duration: 400,
            easing: 'easeInOutQuad'
        });
    } else {
        // Slide in for success
        anime({
            targets: element,
            opacity: [0, 1],
            translateY: [-10, 0],
            duration: TIMING.fast,
            easing: EASE.smooth
        });
    }
}

/**
 * Animate progress bar smoothly
 * @param {HTMLElement} bar - Progress bar element
 * @param {number} percent - Target percentage (0-100)
 */
function animateProgress(bar, percent) {
    if (prefersReducedMotion) {
        bar.style.width = percent + '%';
        return;
    }
    
    anime({
        targets: bar,
        width: percent + '%',
        duration: TIMING.slow,
        easing: EASE.smooth
    });
}

/**
 * Animate count-up effect for numbers
 * @param {HTMLElement} element - Element containing the number
 * @param {number} target - Target number to count to
 * @param {string} suffix - Optional suffix (e.g., '%')
 */
function animateCountUp(element, target, suffix = '') {
    if (prefersReducedMotion) {
        element.textContent = target.toLocaleString() + suffix;
        return;
    }
    
    // Parse current value
    let startVal = 0;
    const currentText = element.textContent.replace(suffix, '').replace(/,/g, '');
    if (!isNaN(parseFloat(currentText))) {
        startVal = parseFloat(currentText);
    }
    
    // If values are same or invalid, just update
    if (startVal === target || isNaN(startVal)) {
        element.textContent = target.toLocaleString() + suffix;
        return;
    }
    
    const obj = { value: startVal };
    anime({
        targets: obj,
        value: target,
        duration: TIMING.slow,
        easing: EASE.smooth,
        round: 1, // Integers only for now
        update: () => {
            element.textContent = obj.value.toLocaleString() + suffix;
        }
    });
}

// Export functions for use in other modules
window.Animations = {
    modalOpen: animateModalOpen,
    modalClose: animateModalClose,
    pageLoad: animatePageLoad,
    cards: animateCards,
    buttonPress: animateButtonPress,
    statusMessage: animateStatusMessage,
    progress: animateProgress,
    countUp: animateCountUp,
    TIMING,
    EASE
};
