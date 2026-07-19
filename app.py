"""
Main Flask Application for NAS Web Interface
"""
import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from pathlib import Path

# Import local modules
from config import *
from models import db, init_db, User, Share, SystemUser, AuditLog, Setting
from auth import init_auth, authenticate_user, change_password, log_action
from samba_manager import SambaManager
from ftp_manager import FTPManager
from system_monitor import SystemMonitor
from nvme_manager import NVMeManager


# Create Flask app
app = Flask(__name__)
app.config.from_object('config')

# Initialize database and authentication
init_db(app)
init_auth(app)

# Initialize managers
samba_mgr = SambaManager()
ftp_mgr = FTPManager()
system_mgr = SystemMonitor()
nvme_mgr = NVMeManager()


# ============================================================================
# Web Routes
# ============================================================================

@app.route('/')
@login_required
def index():
    """Home page - Dashboard"""
    metrics = system_mgr.get_all_metrics()
    samba_status = system_mgr.check_service_status('smbd')
    ftp_status = system_mgr.check_service_status('vsftpd')

    return render_template('index.html',
                         metrics=metrics,
                         samba_status=samba_status,
                         ftp_status=ftp_status)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = authenticate_user(username, password)
        if user:
            login_user(user)
            flash('登录成功！', 'success')
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Logout"""
    log_action(
        username=current_user.username,
        action='logout',
        resource_type='user',
        details='User logged out'
    )
    logout_user()
    flash('已成功登出', 'success')
    return redirect(url_for('login'))


@app.route('/users')
@login_required
def users():
    """User management page"""
    if not current_user.is_admin:
        flash('需要管理员权限', 'error')
        return redirect(url_for('index'))

    all_users = User.query.all()
    return render_template('users.html', users=all_users)


@app.route('/shares')
@login_required
def shares():
    """Share management page"""
    # Get shares from database
    db_shares = Share.query.all()

    # Get shares from Samba configuration
    samba_shares = samba_mgr.parse_shares()

    return render_template('shares.html',
                         db_shares=db_shares,
                         samba_shares=samba_shares)


@app.route('/settings')
@login_required
def settings():
    """Settings page"""
    if not current_user.is_admin:
        flash('需要管理员权限', 'error')
        return redirect(url_for('index'))

    return render_template('settings.html')


@app.route('/nvme')
@login_required
def nvme():
    """NVMe storage management page"""
    devices = nvme_mgr.get_nvme_all()
    temp_summary = nvme_mgr.get_temperature_summary()
    health_summary = nvme_mgr.get_health_summary()
    return render_template('nvme.html',
                         devices=devices,
                         temp_summary=temp_summary,
                         health_summary=health_summary)


# ============================================================================
# API Routes - Authentication
# ============================================================================

@app.route('/api/login', methods=['POST'])
def api_login():
    """API endpoint for login"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = authenticate_user(username, password)
    if user:
        login_user(user)
        return jsonify({'success': True, 'message': 'Login successful'})
    else:
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401


@app.route('/api/logout', methods=['POST'])
@login_required
def api_logout():
    """API endpoint for logout"""
    logout_user()
    return jsonify({'success': True, 'message': 'Logged out'})


@app.route('/api/change-password', methods=['POST'])
@login_required
def api_change_password():
    """API endpoint for password change"""
    data = request.get_json()
    old_password = data.get('old_password')
    new_password = data.get('new_password')

    if change_password(current_user.id, old_password, new_password):
        return jsonify({'success': True, 'message': 'Password changed'})
    else:
        return jsonify({'success': False, 'message': 'Invalid old password'}), 400


# ============================================================================
# API Routes - Users
# ============================================================================

@app.route('/api/users', methods=['GET'])
@login_required
def api_get_users():
    """Get all users"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403

    users = User.query.all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'email': u.email,
        'is_active': u.is_active,
        'is_admin': u.is_admin,
        'created_at': u.created_at.isoformat() if u.created_at else None,
        'last_login': u.last_login.isoformat() if u.last_login else None
    } for u in users])


@app.route('/api/users', methods=['POST'])
@login_required
def api_create_user():
    """Create new user"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403

    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')

    # Check if user exists
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 400

    # Create user
    user = User(username=username, email=email, is_active=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    log_action(
        username=current_user.username,
        action='create_user',
        resource_type='user',
        resource_id=user.id,
        details=f'Created user: {username}'
    )

    return jsonify({'success': True, 'user_id': user.id}), 201


@app.route('/api/users/<int:user_id>', methods=['PUT'])
@login_required
def api_update_user(user_id):
    """Update user"""
    if not current_user.is_admin and current_user.id != user_id:
        return jsonify({'error': 'Access denied'}), 403

    user = User.query.get_or_404(user_id)
    data = request.get_json()

    if 'email' in data:
        user.email = data['email']
    if 'is_active' in data and current_user.is_admin:
        user.is_active = data['is_active']
    if 'is_admin' in data and current_user.is_admin:
        user.is_admin = data['is_admin']

    db.session.commit()

    log_action(
        username=current_user.username,
        action='update_user',
        resource_type='user',
        resource_id=user_id,
        details=f'Updated user: {user.username}'
    )

    return jsonify({'success': True})


@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
def api_delete_user(user_id):
    """Delete user"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403

    user = User.query.get_or_404(user_id)

    if user.username == 'admin':
        return jsonify({'error': 'Cannot delete admin user'}), 400

    log_action(
        username=current_user.username,
        action='delete_user',
        resource_type='user',
        resource_id=user_id,
        details=f'Deleted user: {user.username}'
    )

    db.session.delete(user)
    db.session.commit()

    return jsonify({'success': True})


# ============================================================================
# API Routes - Shares
# ============================================================================

@app.route('/api/shares', methods=['GET'])
@login_required
def api_get_shares():
    """Get all shares"""
    db_shares = Share.query.all()
    samba_shares = samba_mgr.parse_shares()

    return jsonify({
        'database': [{
            'id': s.id,
            'name': s.name,
            'path': s.path,
            'description': s.description,
            'protocol': s.protocol,
            'is_readonly': s.is_readonly,
            'is_public': s.is_public,
            'valid_users': s.valid_users
        } for s in db_shares],
        'samba': samba_shares
    })


@app.route('/api/shares', methods=['POST'])
@login_required
def api_create_share():
    """Create new share"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403

    data = request.get_json()
    name = data.get('name')
    path = data.get('path')
    description = data.get('description', '')
    protocol = data.get('protocol', 'smb')
    readonly = data.get('readonly', False)
    public = data.get('public', False)
    valid_users = data.get('valid_users', '')

    # Validate path
    if not path:
        return jsonify({'error': 'Path is required'}), 400

    # Create directory if not exists
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return jsonify({'error': f'Failed to create directory: {str(e)}'}), 500

    # Create SMB share if requested
    if protocol in ['smb', 'both']:
        if not samba_mgr.create_share(name, path, description, readonly, valid_users):
            return jsonify({'error': 'Failed to create SMB share'}), 500

    # Add to database
    share = Share(
        name=name,
        path=path,
        description=description,
        protocol=protocol,
        is_readonly=readonly,
        is_public=public,
        valid_users=valid_users
    )
    db.session.add(share)
    db.session.commit()

    log_action(
        username=current_user.username,
        action='create_share',
        resource_type='share',
        resource_id=share.id,
        details=f'Created share: {name} at {path}'
    )

    return jsonify({'success': True, 'share_id': share.id}), 201


@app.route('/api/shares/<int:share_id>', methods=['DELETE'])
@login_required
def api_delete_share(share_id):
    """Delete share"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403

    share = Share.query.get_or_404(share_id)

    # Delete from Samba
    if share.protocol in ['smb', 'both']:
        if not samba_mgr.delete_share(share.name):
            return jsonify({'error': 'Failed to delete SMB share'}), 500

    log_action(
        username=current_user.username,
        action='delete_share',
        resource_type='share',
        resource_id=share_id,
        details=f'Deleted share: {share.name}'
    )

    db.session.delete(share)
    db.session.commit()

    return jsonify({'success': True})


# ============================================================================
# API Routes - System
# ============================================================================

@app.route('/api/system/status', methods=['GET'])
@login_required
def api_get_system_status():
    """Get system status"""
    metrics = system_mgr.get_all_metrics()
    samba_status = system_mgr.check_service_status('smbd')
    ftp_status = system_mgr.check_service_status('vsftpd')

    return jsonify({
        'metrics': metrics,
        'services': {
            'samba': samba_status,
            'ftp': ftp_status
        }
    })


@app.route('/api/system/disk', methods=['GET'])
@login_required
def api_get_disk_usage():
    """Get disk usage"""
    path = request.args.get('path', '/')
    usage = system_mgr.get_disk_usage(path)
    return jsonify(usage)


@app.route('/api/system/services/<service_name>/restart', methods=['POST'])
@login_required
def api_restart_service(service_name):
    """Restart a service"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403

    if service_name in ['smbd', 'samba']:
        success = samba_mgr.restart_service()
    elif service_name in ['vsftpd', 'ftp']:
        success = ftp_mgr.restart_service()
    else:
        return jsonify({'error': 'Unknown service'}), 400

    if success:
        log_action(
            username=current_user.username,
            action='restart_service',
            resource_type='system',
            details=f'Restarted service: {service_name}'
        )
        return jsonify({'success': True})
    else:
        return jsonify({'error': f'Failed to restart {service_name}'}), 500


# ============================================================================
# API Routes - NVMe Storage
# ============================================================================

@app.route('/api/nvme', methods=['GET'])
@login_required
def api_get_nvme():
    """Get all NVMe device information"""
    devices = nvme_mgr.get_nvme_all()
    temp_summary = nvme_mgr.get_temperature_summary()
    health_summary = nvme_mgr.get_health_summary()

    return jsonify({
        'devices': devices,
        'temperature': temp_summary,
        'health': health_summary
    })


@app.route('/api/nvme/<device>', methods=['GET'])
@login_required
def api_get_nvme_device(device):
    """Get single NVMe device information"""
    info = nvme_mgr.get_nvme_info(device)
    if info:
        return jsonify(info)
    else:
        return jsonify({'error': 'Device not found'}), 404


@app.route('/api/nvme/<device>/partitions', methods=['GET'])
@login_required
def api_get_nvme_partitions(device):
    """Get partitions for an NVMe device"""
    partitions = nvme_mgr.get_partitions(device)
    return jsonify({'device': device, 'partitions': partitions})


@app.route('/api/nvme/<device>/mount', methods=['POST'])
@login_required
def api_mount_nvme(device):
    """Mount an NVMe partition"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403

    data = request.get_json()
    mount_point = data.get('mount_point')

    if not mount_point:
        return jsonify({'error': 'Mount point required'}), 400

    success, message = nvme_mgr.mount_nvme(device, mount_point)

    if success:
        log_action(
            username=current_user.username,
            action='mount_nvme',
            resource_type='storage',
            details=f'Mounted {device} at {mount_point}'
        )
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'error': message}), 400


@app.route('/api/nvme/<device>/unmount', methods=['POST'])
@login_required
def api_unmount_nvme(device):
    """Unmount an NVMe partition"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403

    data = request.get_json()
    mount_point = data.get('mount_point')

    if not mount_point:
        return jsonify({'error': 'Mount point required'}), 400

    success, message = nvme_mgr.unmount_nvme(mount_point)

    if success:
        log_action(
            username=current_user.username,
            action='unmount_nvme',
            resource_type='storage',
            details=f'Unmounted {device} from {mount_point}'
        )
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'error': message}), 400


@app.route('/api/nvme/<device>/format', methods=['POST'])
@login_required
def api_format_nvme(device):
    """Format an NVMe partition"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403

    data = request.get_json()
    fstype = data.get('fstype', 'ext4')

    success, message = nvme_mgr.format_nvme(device, fstype)

    if success:
        log_action(
            username=current_user.username,
            action='format_nvme',
            resource_type='storage',
            details=f'Formatted {device} as {fstype}'
        )
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'error': message}), 400


@app.route('/api/nvme/storage', methods=['GET'])
@login_required
def api_get_nvme_storage():
    """Get storage space info for all NVMe drives"""
    storage = nvme_mgr.get_storage_info()
    return jsonify(storage)


# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found_error(error):
    """404 error handler"""
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """500 error handler"""
    return jsonify({'error': 'Internal server error'}), 500


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == '__main__':
    # Create database directory if not exists
    db_path = Path(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Create log directory if not exists
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

    # Run the app
    app.run(
        host=WEB_HOST,
        port=WEB_PORT,
        debug=True
    )