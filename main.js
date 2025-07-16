// Main JavaScript for Parking Management System
document.addEventListener('DOMContentLoaded', function() {
    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            alert.style.opacity = '0';
            setTimeout(function() {
                alert.remove();
            }, 500);
        }, 5000);
    });

    // Confirmation for dangerous actions
    const dangerButtons = document.querySelectorAll('.btn-danger');
    dangerButtons.forEach(function(button) {
        if (button.textContent.includes('Delete') || button.textContent.includes('Release')) {
            button.addEventListener('click', function(e) {
                if (!confirm('Are you sure you want to proceed?')) {
                    e.preventDefault();
                }
            });
        }
    });
});