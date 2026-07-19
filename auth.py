"""
Authentication module for NAS Web Application
"""
from flask import request, current_app
from flask_login import LoginManager
from datetime import datetime
from models import db, User, AuditLog

login_manager = LoginManager()


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    return User.query.get(int(user_id))


def init_auth(app):
    """Initialize authentication"""
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    login_manager.login_message = '请登录以访问此页面'
    login_manager.session_protection = 'strong'


def authenticate_user(username, password):
    """
    Authenticate user credentials
    Returns: User object if successful, None otherwise
    """
    user = User.query.filter_by(username=username).first()

    if user and user.is_active and user.check_password(password):
        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()

        # Log successful login
        log_action(
            username=username,
            action='login',
            resource_type='user',
            details='Successful login'
        )

        return user

    # Log failed login attempt
    if username:
        log_action(
            username=username,
            action='login_failed',
            resource_type='user',
            details='Failed login attempt'
        )

    return None


def change_password(user_id, old_password, new_password):
    """
    Change user password
    Returns: True if successful, False otherwise
    """
    user = User.query.get(user_id)

    if user and user.check_password(old_password):
        user.set_password(new_password)
        db.session.commit()

        log_action(
            username=user.username,
            action='password_change',
            resource_type='user',
            resource_id=user.id,
            details='Password changed successfully'
        )

        return True

    return False


def log_action(username, action, resource_type, resource_id=None, details=None):
    """Log user action to audit log"""
    try:
        log = AuditLog(
            username=username,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=request.remote_addr if request else None
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Failed to log action: {e}")
        db.session.rollback()