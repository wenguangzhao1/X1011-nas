"""
Configuration file for NAS Web Application
"""
import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Flask configuration
SECRET_KEY = os.environ.get('SECRET_KEY') or 'nas-web-secret-key-change-in-production'

# Database configuration
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
    f'sqlite:///{BASE_DIR / "nas.db"}'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Samba configuration
SAMBA_CONFIG_PATH = '/etc/samba/smb.conf'
SAMBA_BACKUP_DIR = '/etc/samba/backups'

# FTP configuration
VSFTPD_CONFIG_PATH = '/etc/vsftpd.conf'
VSFTPD_USERLIST_PATH = '/etc/vsftpd.userlist'

# Storage configuration
STORAGE_BASE_DIR = Path('/mnt/nvme0/shares')

# Admin user credentials (first-time setup)
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'  # Should be changed on first login

# Security settings
LOGIN_DISABLED = False
SESSION_LIFETIME = 3600  # 1 hour in seconds

# Logging configuration
LOG_DIR = os.path.expanduser('~/nas-web-logs')  # TF card for logs
LOG_MAX_BYTES = 10485760  # 10 MB
LOG_BACKUP_COUNT = 5

# Service names
SAMBA_SERVICE = 'smbd'
FTP_SERVICE = 'vsftpd'
WEB_SERVICE = 'nas-web'

# Network settings
WEB_HOST = '0.0.0.0'  # Listen on all interfaces (LAN access)
WEB_PORT = 5000