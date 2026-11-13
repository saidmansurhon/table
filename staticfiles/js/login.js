// Toggle password visibility
const togglePassword = document.getElementById('togglePassword');
const passwordInput = document.getElementById('password');

if (togglePassword) {
    togglePassword.addEventListener('click', function() {
        const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
        passwordInput.setAttribute('type', type);
        
        // Toggle eye icon
        const eyeIcon = this.querySelector('.eye-icon');
        if (type === 'text') {
            eyeIcon.innerHTML = `
                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                <line x1="1" y1="1" x2="23" y2="23"/>
            `;
        } else {
            eyeIcon.innerHTML = `
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                <circle cx="12" cy="12" r="3"/>
            `;
        }
    });
}

// Form submission with loading state
const loginForm = document.getElementById('loginForm');
const loginBtn = document.getElementById('loginBtn');

if (loginForm) {
    loginForm.addEventListener('submit', function(e) {
        // Add loading state
        loginBtn.classList.add('loading');
        loginBtn.disabled = true;
        
        // Form will submit normally, but if there's an error, remove loading state
        setTimeout(() => {
            if (document.querySelector('.alert-error')) {
                loginBtn.classList.remove('loading');
                loginBtn.disabled = false;
                
                // Shake animation on error
                const loginCard = document.querySelector('.login-card');
                loginCard.classList.add('shake');
                setTimeout(() => {
                    loginCard.classList.remove('shake');
                }, 500);
            }
        }, 100);
    });
}

// Input focus animations
const inputs = document.querySelectorAll('.form-input');

inputs.forEach(input => {
    // Add placeholder attribute for floating label to work
    input.setAttribute('placeholder', ' ');
    
    input.addEventListener('focus', function() {
        this.parentElement.style.transform = 'scale(1.02)';
    });
    
    input.addEventListener('blur', function() {
        this.parentElement.style.transform = 'scale(1)';
    });
});

// Smooth entrance animation
window.addEventListener('load', () => {
    document.body.style.opacity = '0';
    setTimeout(() => {
        document.body.style.transition = 'opacity 0.5s ease';
        document.body.style.opacity = '1';
    }, 100);
});

// Add ripple effect to button
loginBtn.addEventListener('click', function(e) {
    const rect = this.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    const ripple = document.createElement('span');
    ripple.style.position = 'absolute';
    ripple.style.left = x + 'px';
    ripple.style.top = y + 'px';
    ripple.style.width = '0';
    ripple.style.height = '0';
    ripple.style.borderRadius = '50%';
    ripple.style.background = 'rgba(255, 255, 255, 0.5)';
    ripple.style.transform = 'translate(-50%, -50%)';
    ripple.style.animation = 'ripple 0.6s ease-out';
    
    this.appendChild(ripple);
    
    setTimeout(() => ripple.remove(), 600);
});

// Add ripple animation
const style = document.createElement('style');
style.textContent = `
    @keyframes ripple {
        to {
            width: 300px;
            height: 300px;
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Auto-dismiss alerts after 5 seconds
const alerts = document.querySelectorAll('.alert');
alerts.forEach(alert => {
    setTimeout(() => {
        alert.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        alert.style.opacity = '0';
        alert.style.transform = 'translateX(20px)';
        setTimeout(() => alert.remove(), 300);
    }, 5000);
});
