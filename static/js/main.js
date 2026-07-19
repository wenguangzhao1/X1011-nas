/**
 * NAS Web Application - Main JavaScript
 */

// Show change password modal
function showChangePasswordModal() {
    const modal = new bootstrap.Modal(document.getElementById('changePasswordModal'));
    modal.show();
}

// Change password
function changePassword() {
    const form = document.getElementById('changePasswordForm');
    const formData = new FormData(form);

    const oldPassword = formData.get('old_password');
    const newPassword = formData.get('new_password');
    const confirmPassword = formData.get('confirm_password');

    // Validate
    if (!oldPassword || !newPassword || !confirmPassword) {
        alert('请填写所有字段');
        return;
    }

    if (newPassword !== confirmPassword) {
        alert('新密码不匹配');
        return;
    }

    // Send request
    fetch('/api/change-password', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            old_password: oldPassword,
            new_password: newPassword
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('密码修改成功');
            bootstrap.Modal.getInstance(document.getElementById('changePasswordModal')).hide();
            form.reset();
        } else {
            alert('密码修改失败: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('密码修改失败');
    });
}

// Utility function: Format bytes to human readable
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];

    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

// Utility function: Format date
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('zh-CN');
}

// Show loading spinner
function showLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = '<i class="bi bi-hourglass-split"></i> 加载中...';
        element.classList.add('status-updating');
    }
}

// Hide loading spinner
function hideLoading(elementId, content) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = content;
        element.classList.remove('status-updating');
    }
}

// Show toast notification
function showToast(message, type = 'info') {
    // Create toast container if not exists
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(container);
    }

    // Create toast
    const toastHtml = `
        <div class="toast align-items-center text-white bg-${type === 'error' ? 'danger' : type}" role="alert">
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;

    container.innerHTML += toastHtml;

    // Show toast
    const toastElement = container.lastElementChild;
    const toast = new bootstrap.Toast(toastElement);
    toast.show();
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('NAS Web Application initialized');

    // Add any global initialization here
});