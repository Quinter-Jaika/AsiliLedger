/**
 * Timber Tracker - African Alternative Vibe
 * Handles sidebar toggling, mobile responsiveness, and UI interactions
 */

(function() {
    'use strict';

    // DOM Elements
    const toggleBtn = document.getElementById('sidebarToggle');
    const sidebarEl = document.getElementById('sidebar');
    const logoutLink = document.getElementById('logoutLink');
    const sidebarLogoutLink = document.getElementById('sidebarLogoutLink');
    const MOBILE_BREAKPOINT = 992;

    let overlay = null;

    /**
     * Check if current viewport is mobile
     * @returns {boolean}
     */
    function isMobile() {
        return window.innerWidth <= MOBILE_BREAKPOINT;
    }

    function createOverlay() {
        if (overlay) return;

        overlay = document.createElement('div');
        overlay.className = 'sidebar-overlay';
        overlay.addEventListener('click', closeSidebar);
        document.body.appendChild(overlay);

        requestAnimationFrame(() => {
            if (overlay) {
                overlay.classList.add('show');
            }
        });
    }

    function removeOverlay() {
        if (!overlay) return;

        overlay.classList.remove('show');

        setTimeout(() => {
            if (overlay) {
                overlay.removeEventListener('click', closeSidebar);
                overlay.remove();
                overlay = null;
            }
        }, 250);

        document.body.classList.remove('sidebar-open');
    }

    function openSidebar() {
        if (!sidebarEl) return;

        if (isMobile()) {
            sidebarEl.classList.add('show-mobile');
            document.body.classList.add('sidebar-open');
            createOverlay();
        } else {
            document.body.classList.remove('sidebar-collapsed');
        }
    }

    function closeSidebar() {
        if (!sidebarEl) return;

        if (isMobile()) {
            sidebarEl.classList.remove('show-mobile');
            removeOverlay();
        } else {
            document.body.classList.add('sidebar-collapsed');
        }
    }

    /**
     * Handle sidebar toggle button click.
     * Mobile: slide the off-canvas panel in/out.
     * Desktop: collapse/expand via a body class
     */
    function handleToggle(e) {
        e.preventDefault();
        e.stopPropagation();

        if (!sidebarEl) return;

        if (isMobile()) {
            if (sidebarEl.classList.contains('show-mobile')) {
                closeSidebar();
            } else {
                openSidebar();
            }
        } else {
            document.body.classList.toggle('sidebar-collapsed');
        }
    }

    /**
     * Handle window resize to adjust sidebar state
     */
    function handleResize() {
        if (!sidebarEl) return;

        if (isMobile()) {
            // Mobile: sidebar is closed unless show-mobile exists.
            document.body.classList.remove('sidebar-collapsed');
        } else {
            // Desktop: remove all mobile state.
            sidebarEl.classList.remove('show-mobile');
            removeOverlay();
        }
    }

    /**
     * Initialize active navigation link highlighting
     */
    function initActiveNavigation() {
        const currentPath = window.location.pathname;
        const navLinks = document.querySelectorAll('.sidebar .nav-link');

        navLinks.forEach(link => {
            const href = link.getAttribute('href');
            if (href && href !== '#' && currentPath.includes(href)) {
                navLinks.forEach(l => l.classList.remove('active'));
                link.classList.add('active');
            }
        });
    }

    /**
     * Handle logout functionality
     */
    function initLogoutHandler() {
        const logoutLinks = [
            { element: logoutLink, selector: '#logoutLink' },
            { element: sidebarLogoutLink, selector: '#sidebarLogoutLink' }
        ];

        logoutLinks.forEach(({ element }) => {
            if (element) {
                element.addEventListener('click', function(e) {
                    e.preventDefault();
                    if (confirm('Are you sure you want to logout?')) {
                        // Add your logout logic here
                        console.log('User logged out');
                        // window.location.href = '/logout';
                    }
                });
            }
        });
    }

    /**
     * Add smooth scrolling to anchor links
     */
    function initSmoothScrolling() {
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function(e) {
                const targetId = this.getAttribute('href');
                if (targetId && targetId !== '#') {
                    const targetElement = document.querySelector(targetId);
                    if (targetElement) {
                        e.preventDefault();
                        targetElement.scrollIntoView({
                            behavior: 'smooth',
                            block: 'start'
                        });
                    }
                }
            });
        });
    }

    /**
     * Add animation to cards on scroll (subtle fade-in)
     */
    function initScrollAnimations() {
        const cards = document.querySelectorAll('.card');

        const observerOptions = {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                    observer.unobserve(entry.target);
                }
            });
        }, observerOptions);

        cards.forEach(card => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(20px)';
            card.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            observer.observe(card);
        });
    }

    /**
     * Handle sidebar click to prevent closing when clicking inside
     */
    function initSidebarClickProtection() {
        if (sidebarEl) {
            sidebarEl.addEventListener('click', function(e) {
                e.stopPropagation();
            });
        }
    }

    /**
     * Add keyboard support (ESC to close sidebar on mobile)
     */
    function initKeyboardSupport() {
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && isMobile() && sidebarEl && sidebarEl.classList.contains('show-mobile')) {
                closeSidebar();
            }
        });
    }

    /**
     * Initialize tooltips if Bootstrap is available
     */
    function initTooltips() {
        if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
            const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            tooltipTriggerList.map(function(tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
        }
    }

    /**
     * Set current year in footer if element exists
     */
    function updateFooterYear() {
        const yearElement = document.querySelector('.footer-year');
        if (yearElement) {
            yearElement.textContent = new Date().getFullYear();
        }
    }

    /**
     * Add hover effects for social icons
     */
    function initSocialIcons() {
        const socialIcons = document.querySelectorAll('.social-icons i');
        socialIcons.forEach(icon => {
            icon.addEventListener('mouseenter', function() {
                this.style.transform = 'translateY(-3px)';
            });
            icon.addEventListener('mouseleave', function() {
                this.style.transform = 'translateY(0)';
            });
        });
    }

    /**
     * Initialize sidebar state on page load
     */
    function initSidebarState() {
        if (!sidebarEl) return;

        sidebarEl.classList.remove('show-mobile');
        document.body.classList.remove('sidebar-open');

        if (isMobile()) {
            document.body.classList.remove('sidebar-collapsed');
        }
    }

    // Initialize all functionality when DOM is ready
    document.addEventListener('DOMContentLoaded', function() {
        // Initialize sidebar state
        initSidebarState();

        // Sidebar toggle
        if (toggleBtn) {
            toggleBtn.addEventListener('click', handleToggle);
        }

        // Window resize handler
        window.addEventListener('resize', handleResize);

        // Navigation active state
        initActiveNavigation();

        // Logout handler
        initLogoutHandler();

        // Smooth scrolling
        initSmoothScrolling();

        // Scroll animations
        initScrollAnimations();

        // Sidebar click protection
        initSidebarClickProtection();

        // Keyboard support
        initKeyboardSupport();

        // Bootstrap tooltips
        initTooltips();

        // Footer year update
        updateFooterYear();

        // Social icons
        initSocialIcons();

        console.log('Sidebar initialized');
        console.log('Mobile:', isMobile());
        console.log('Toggle:', toggleBtn);
        console.log('Sidebar:', sidebarEl);
    });

    // Export functions for debugging (optional)
    window.timberTracker = {
        openSidebar,
        closeSidebar,
        isMobile,
        toggle: handleToggle
    };
})();