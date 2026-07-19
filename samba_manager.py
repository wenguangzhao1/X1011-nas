"""
Samba configuration management module
"""
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from flask import current_app
import re


class SambaManager:
    """Manage Samba configuration and shares"""

    def __init__(self, config_path=None, backup_dir=None):
        # Delay accessing current_app until needed
        self._config_path = config_path
        self._backup_dir = backup_dir

    @property
    def config_path(self):
        if self._config_path is None:
            try:
                from flask import current_app
                self._config_path = current_app.config.get('SAMBA_CONFIG_PATH', '/etc/samba/smb.conf')
            except:
                self._config_path = '/etc/samba/smb.conf'
        return self._config_path

    @property
    def backup_dir(self):
        if self._backup_dir is None:
            try:
                from flask import current_app
                self._backup_dir = current_app.config.get('SAMBA_BACKUP_DIR', '/etc/samba/backups')
            except:
                self._backup_dir = '/etc/samba/backups'
        # Ensure backup directory exists
        Path(self._backup_dir).mkdir(parents=True, exist_ok=True)
        return self._backup_dir

    def backup_config(self):
        """Create a backup of the Samba configuration"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(self.backup_dir, f'smb.conf.backup.{timestamp}')
        shutil.copy2(self.config_path, backup_path)
        current_app.logger.info(f"Created backup: {backup_path}")
        return backup_path

    def read_config(self):
        """Read the entire Samba configuration file"""
        try:
            with open(self.config_path, 'r') as f:
                return f.read()
        except Exception as e:
            current_app.logger.error(f"Failed to read config: {e}")
            return None

    def parse_shares(self):
        """
        Parse Samba configuration and extract share information
        Returns: dict of shares
        """
        config_content = self.read_config()
        if not config_content:
            return {}

        shares = {}
        current_share = None
        share_config = {}

        for line in config_content.split('\n'):
            # Match share header [share_name]
            share_match = re.match(r'^\[([^\]]+)\]$', line)
            if share_match:
                # Save previous share if exists
                if current_share and current_share not in ['global', 'homes', 'printers', 'print$']:
                    shares[current_share] = share_config

                # Start new share
                current_share = share_match.group(1)
                share_config = {}
                continue

            # Parse key = value lines
            if current_share and '=' in line:
                line = line.strip()
                if not line.startswith('#') and not line.startswith(';'):
                    key, value = line.split('=', 1)
                    share_config[key.strip()] = value.strip()

        # Don't forget the last share
        if current_share and current_share not in ['global', 'homes', 'printers', 'print$']:
            shares[current_share] = share_config

        return shares

    def validate_config(self):
        """Validate Samba configuration using testparm"""
        try:
            result = subprocess.run(
                ['sudo', 'testparm', '-s'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                current_app.logger.info("Samba configuration is valid")
                return True
            else:
                current_app.logger.error(f"Invalid Samba configuration: {result.stderr}")
                return False
        except Exception as e:
            current_app.logger.error(f"Failed to validate config: {e}")
            return False

    def restart_service(self):
        """Restart Samba services"""
        try:
            subprocess.run(['sudo', 'systemctl', 'restart', 'smbd'], check=True, timeout=30)
            subprocess.run(['sudo', 'systemctl', 'restart', 'nmbd'], check=True, timeout=30)
            current_app.logger.info("Samba services restarted successfully")
            return True
        except Exception as e:
            current_app.logger.error(f"Failed to restart Samba: {e}")
            return False

    def create_share(self, name, path, comment='', readonly=False, valid_users=None):
        """
        Create a new Samba share
        Args:
            name: Share name
            path: Path to shared directory
            comment: Share description
            readonly: Read-only flag
            valid_users: Comma-separated list of valid users
        Returns: True if successful, False otherwise
        """
        # Validate share name
        if not name or not re.match(r'^[a-zA-Z0-9_-]+$', name):
            current_app.logger.error(f"Invalid share name: {name}")
            return False

        # Check if share already exists
        shares = self.parse_shares()
        if name in shares:
            current_app.logger.error(f"Share already exists: {name}")
            return False

        # Create directory if not exists
        Path(path).mkdir(parents=True, exist_ok=True)

        # Set directory permissions
        try:
            os.chmod(path, 0o2770)  # rwxrws---
            subprocess.run(['sudo', 'chown', 'root:users', path], check=True)
        except Exception as e:
            current_app.logger.error(f"Failed to set permissions: {e}")
            return False

        # Backup existing config
        self.backup_config()

        # Build share configuration
        share_config = f"\n[{name}]\n"
        share_config += f"   path = {path}\n"
        if comment:
            share_config += f"   comment = {comment}\n"
        share_config += f"   browseable = yes\n"
        share_config += f"   read only = {'yes' if readonly else 'no'}\n"
        share_config += f"   create mask = 0770\n"
        share_config += f"   directory mask = 0770\n"
        if valid_users:
            share_config += f"   valid users = {valid_users}\n"
        else:
            share_config += f"   guest ok = yes\n"

        # Append to config file
        try:
            with open(self.config_path, 'a') as f:
                f.write(share_config)

            # Validate and restart
            if self.validate_config():
                self.restart_service()
                current_app.logger.info(f"Created share: {name}")
                return True
            else:
                # Restore backup if validation fails
                self.restore_last_backup()
                return False

        except Exception as e:
            current_app.logger.error(f"Failed to create share: {e}")
            self.restore_last_backup()
            return False

    def modify_share(self, name, **kwargs):
        """
        Modify an existing Samba share
        Args:
            name: Share name
            kwargs: Configuration parameters to update
        Returns: True if successful, False otherwise
        """
        shares = self.parse_shares()
        if name not in shares:
            current_app.logger.error(f"Share not found: {name}")
            return False

        # Backup existing config
        self.backup_config()

        # Read entire config
        config_content = self.read_config()
        lines = config_content.split('\n')

        # Find and modify the share
        in_target_share = False
        new_lines = []

        for line in lines:
            if re.match(rf'^\[{re.escape(name)}\]$', line):
                in_target_share = True
                new_lines.append(line)
            elif in_target_share and re.match(r'^\[', line):
                # End of target share
                in_target_share = False
                new_lines.append(line)
            elif in_target_share:
                # Modify or keep existing parameter
                modified = False
                for key, value in kwargs.items():
                    if line.strip().startswith(f'{key} ='):
                        new_lines.append(f"   {key} = {value}\n")
                        modified = True
                        break
                if not modified:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        # Write modified config
        try:
            with open(self.config_path, 'w') as f:
                f.write('\n'.join(new_lines))

            # Validate and restart
            if self.validate_config():
                self.restart_service()
                current_app.logger.info(f"Modified share: {name}")
                return True
            else:
                self.restore_last_backup()
                return False

        except Exception as e:
            current_app.logger.error(f"Failed to modify share: {e}")
            self.restore_last_backup()
            return False

    def delete_share(self, name):
        """
        Delete a Samba share (keeps data)
        Args:
            name: Share name
        Returns: True if successful, False otherwise
        """
        shares = self.parse_shares()
        if name not in shares:
            current_app.logger.error(f"Share not found: {name}")
            return False

        # Backup existing config
        self.backup_config()

        # Read entire config
        config_content = self.read_config()
        lines = config_content.split('\n')

        # Remove the share section
        in_target_share = False
        new_lines = []

        for line in lines:
            if re.match(rf'^\[{re.escape(name)}\]$', line):
                in_target_share = True
                continue
            elif in_target_share and re.match(r'^\[', line):
                in_target_share = False
                new_lines.append(line)
            elif not in_target_share:
                new_lines.append(line)

        # Write modified config
        try:
            with open(self.config_path, 'w') as f:
                f.write('\n'.join(new_lines))

            # Validate and restart
            if self.validate_config():
                self.restart_service()
                current_app.logger.info(f"Deleted share: {name}")
                return True
            else:
                self.restore_last_backup()
                return False

        except Exception as e:
            current_app.logger.error(f"Failed to delete share: {e}")
            self.restore_last_backup()
            return False

    def restore_last_backup(self):
        """Restore the most recent backup"""
        backup_files = sorted(
            Path(self.backup_dir).glob('smb.conf.backup.*'),
            key=os.path.getmtime,
            reverse=True
        )

        if backup_files:
            last_backup = backup_files[0]
            shutil.copy2(last_backup, self.config_path)
            current_app.logger.info(f"Restored backup: {last_backup}")
            return True

        return False

    def get_connections(self):
        """Get active Samba connections"""
        try:
            result = subprocess.run(
                ['sudo', 'smbstatus', '-b'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                # Parse output to count connections
                lines = result.stdout.strip().split('\n')
                # Filter out header lines
                connections = [line for line in lines if line and not line.startswith('Samba')]
                return len(connections)
        except Exception as e:
            current_app.logger.error(f"Failed to get connections: {e}")

        return 0