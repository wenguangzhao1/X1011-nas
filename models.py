"""
Database models for NAS Web Application
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model, UserMixin):
    """User model for web interface authentication"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


class Share(db.Model):
    """Share model for storing shared folder configurations"""
    __tablename__ = 'shares'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    path = db.Column(db.String(255), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    protocol = db.Column(db.String(20), nullable=False)  # 'smb', 'ftp', or 'both'
    is_readonly = db.Column(db.Boolean, default=False)
    is_public = db.Column(db.Boolean, default=False)
    valid_users = db.Column(db.Text, nullable=True)  # Comma-separated usernames
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Share {self.name}>'


class SystemUser(db.Model):
    """System user model for tracking Linux system users managed by NAS"""
    __tablename__ = 'system_users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    samba_enabled = db.Column(db.Boolean, default=False)
    ftp_enabled = db.Column(db.Boolean, default=False)
    home_directory = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<SystemUser {self.username}>'


class Setting(db.Model):
    """Key-value settings storage"""
    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Setting {self.key}={self.value}>'


class AuditLog(db.Model):
    """Audit log for tracking user actions"""
    __tablename__ = 'audit_log'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    resource_type = db.Column(db.String(50), nullable=False)  # 'user', 'share', 'system'
    resource_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<AuditLog {self.username} - {self.action}>'


def init_db(app):
    """Initialize database"""
    db.init_app(app)
    with app.app_context():
        db.create_all()

        # Create default admin user if not exists
        from config import ADMIN_USERNAME, ADMIN_PASSWORD
        admin = User.query.filter_by(username=ADMIN_USERNAME).first()
        if not admin:
            admin = User(
                username=ADMIN_USERNAME,
                email='admin@nas.local',
                is_admin=True,
                is_active=True
            )
            admin.set_password(ADMIN_PASSWORD)
            db.session.add(admin)
            db.session.commit()
            print(f"Created default admin user: {ADMIN_USERNAME}")