# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NAS Web Application - A Flask-based web interface for managing a Network Attached Storage server on Raspberry Pi. Provides management for Samba shares, FTP access, NVMe storage devices, and system monitoring.

## Common Commands

### Running the Application

```bash
# Start the server (from project root)
python3 app.py

# Or use the startup script (runs in background)
./start-nas.sh

# Stop the server
pkill -f "python3 app.py"
```

The application runs on `http://0.0.0.0:5000` by default (configurable in `config.py`).

### Development Setup

```bash
# Install dependencies
pip3 install -r requirements.txt

# Initialize database (happens automatically on first run)
# Default admin credentials: admin / admin123
python3 app.py
```

### Database Management

```bash
# Database location: ./nas.db (SQLite)
# The database is auto-created on first run with default admin user

# To reset database: delete nas.db and restart the app
rm nas.db
python3 app.py
```

## Architecture

### Backend Structure

**Manager Classes** - Each manager handles a specific subsystem:
- `SambaManager` (`samba_manager.py`) - Manages Samba/SMB share configuration via `/etc/samba/smb.conf`
- `FTPManager` (`ftp_manager.py`) - Manages vsftpd configuration
- `NVMeManager` (`nvme_manager.py`) - NVMe device monitoring, mounting, formatting via `smartctl`, `lsblk`, `nvme` CLI tools
- `SystemMonitor` (`system_monitor.py`) - System metrics (CPU, memory, disk) via `psutil` and `/proc`

**Models** (`models.py`):
- `User` - Web interface authentication
- `Share` - Shared folder configurations
- `SystemUser` - Linux system user tracking
- `AuditLog` - Action logging
- `Setting` - Key-value configuration storage

**Authentication** (`auth.py`):
- Flask-Login for session management
- Password hashing with Werkzeug
- Audit logging for login/logout/password changes

### Frontend Structure

- Templates: Jinja2 templates using Bootstrap 5 and Bootstrap Icons
- Static files: Custom CSS in `static/css/style.css`, JavaScript in `static/js/main.js`
- UI is in Chinese (zh-CN)

### API Design

RESTful API endpoints under `/api/`:
- `/api/users` - User CRUD operations
- `/api/shares` - Share management
- `/api/system/status` - System metrics
- `/api/nvme/*` - NVMe device operations

All API endpoints require authentication via Flask-Login session. Admin-only operations check `current_user.is_admin`.

### Configuration

Configuration in `config.py`:
- `SECRET_KEY` - Flask session secret (should change in production)
- `SQLALCHEMY_DATABASE_URI` - SQLite database path
- `SAMBA_CONFIG_PATH` - Path to smb.conf
- `WEB_HOST/WEB_PORT` - Server binding
- `LOG_DIR` - Application logs directory

## Key Implementation Details

### Samba Share Management

- Parses and modifies `/etc/samba/smb.conf` directly
- Creates backups before modifications in `/etc/samba/backups/`
- Validates config with `testparm` before applying
- Requires `sudo` privileges for service restart

### NVMe Management

- Uses `smartctl` (via sudo) for health/temperature data
- Mounts/unmounts partitions via system commands
- Supports formatting partitions (ext4, xfs, etc.)
- Temperature thresholds: warning at 70°C, critical at 80°C

### Storage Layout

Application and logs stored on TF card:
- App: `~/nas-web/`
- Logs: `~/nas-web-logs/`
- Database: `~/nas-web/nas.db`

User data stored on NVMe drives:
- `/mnt/nvme0/shares`, `/mnt/nvme1/shares`, etc.

### Security Considerations

- Default admin password (`admin123`) should be changed immediately
- Samba/FTP managers require sudo access for system configuration
- Sessions expire after 1 hour (`SESSION_LIFETIME = 3600`)
- All sensitive actions are logged to `AuditLog`

## Dependencies

Main Python packages (see `requirements.txt`):
- Flask 2.2.2+
- Flask-Login 0.6.3
- Flask-SQLAlchemy 3.1.1
- Werkzeug 2.2.2+
- python-dotenv 1.0.0
- psutil 5.9.4

System dependencies:
- `smbd` - Samba daemon
- `vsftpd` - FTP server
- `smartctl` - NVMe health monitoring
- `nvme` CLI - NVMe management
- `sudo` - For system operations

## Language

UI and comments are in Chinese. Error messages and log entries mix Chinese and English.

## NVMe 散热优化

### 问题
闲置状态下 NVMe 温度可达 67-70°C，原因：
- NVMe 扩展板无散热片
- 电源管理默认未启用

### 已配置优化
1. **系统服务**: `/etc/systemd/system/nvme-power-save.service`
   - 启用 NVMe 自动电源管理
   - 设置低功耗电源状态 (PS 3: 0.07W)

2. **内核参数**: `/boot/firmware/cmdline.txt`
   - `nvme_core.default_ps_max_latency_us=55000`

### 验证命令
```bash
# 检查温度
sudo smartctl -A /dev/nvme{0..3} | grep Temperature

# 检查电源状态
sudo nvme get-feature -f 0x02 -H /dev/nvme0

# 检查服务
systemctl status nvme-power-save.service
```

### 硬件建议
- 推荐安装 NVMe 散热马甲（降温 10-15°C）
- 搜索关键词：`NVMe散热马甲`、`M.2散热片`