"""
FTP (vsftpd) configuration management module
"""
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from flask import current_app


class FTPManager:
    """Manage vsftpd configuration and users"""

    def __init__(self, config_path=None, userlist_path=None):
        # Delay accessing current_app until needed
        self._config_path = config_path
        self._userlist_path = userlist_path

    @property
    def config_path(self):
        if self._config_path is None:
            try:
                from flask import current_app
                self._config_path = current_app.config.get('VSFTPD_CONFIG_PATH', '/etc/vsftpd.conf')
            except:
                self._config_path = '/etc/vsftpd.conf'
        return self._config_path

    @property
    def userlist_path(self):
        if self._userlist_path is None:
            try:
                from flask import current_app
                self._userlist_path = current_app.config.get('VSFTPD_USERLIST_PATH', '/etc/vsftpd.userlist')
            except:
                self._userlist_path = '/etc/vsftpd.userlist'
        return self._userlist_path

    def read_config(self):
        """Read vsftpd configuration file"""
        try:
            with open(self.config_path, 'r') as f:
                return f.read()
        except Exception as e:
            current_app.logger.error(f"Failed to read FTP config: {e}")
            return None

    def parse_config(self):
        """Parse vsftpd configuration into dictionary"""
        config_content = self.read_config()
        if not config_content:
            return {}

        config = {}
        for line in config_content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()

        return config

    def configure_ftp(self):
        """
        Configure vsftpd for NAS use
        Returns: True if successful, False otherwise
        """
        # Backup existing config
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{self.config_path}.backup.{timestamp}"
        try:
            shutil.copy2(self.config_path, backup_path)
        except Exception as e:
            current_app.logger.warning(f"Could not backup config: {e}")

        # Default vsftpd configuration for NAS
        config_lines = [
            "# vsftpd configuration for NAS",
            "# Basic settings",
            "listen=NO",
            "listen_ipv6=YES",
            "anonymous_enable=NO",
            "local_enable=YES",
            "write_enable=YES",
            "local_umask=022",
            "dirmessage_enable=YES",
            "use_localtime=YES",
            "xferlog_enable=YES",
            "connect_from_port_20=YES",
            "",
            "# Security settings",
            "chroot_local_user=YES",
            "chroot_list_enable=NO",
            "allow_writeable_chroot=YES",
            "secure_chroot_dir=/var/run/vsftpd/empty",
            "pam_service_name=vsftpd",
            "",
            "# User settings",
            "userlist_enable=YES",
            f"userlist_file={self.userlist_path}",
            "userlist_deny=NO",  # Allow only listed users
            "",
            "# Performance settings",
            "idle_session_timeout=600",
            "data_connection_timeout=120",
            "",
            "# Logging",
            "dual_log_enable=YES",
            "log_ftp_protocol=YES",
            f"vsftpd_log_file=/var/log/vsftpd.log",
            f"xferlog_file=/var/log/xferlog",
        ]

        try:
            with open(self.config_path, 'w') as f:
                f.write('\n'.join(config_lines))

            current_app.logger.info("Configured vsftpd for NAS")
            return self.restart_service()
        except Exception as e:
            current_app.logger.error(f"Failed to configure vsftpd: {e}")
            return False

    def restart_service(self):
        """Restart vsftpd service"""
        try:
            subprocess.run(['sudo', 'systemctl', 'restart', 'vsftpd'], check=True, timeout=30)
            current_app.logger.info("vsftpd service restarted")
            return True
        except Exception as e:
            current_app.logger.error(f"Failed to restart vsftpd: {e}")
            return False

    def add_user_to_list(self, username):
        """
        Add user to vsftpd user list
        Args:
            username: System username to add
        Returns: True if successful, False otherwise
        """
        # Read existing user list
        users = self.get_user_list()

        # Add user if not exists
        if username not in users:
            users.append(username)

            # Write updated user list
            try:
                with open(self.userlist_path, 'w') as f:
                    f.write('\n'.join(users) + '\n')

                current_app.logger.info(f"Added {username} to FTP user list")
                return True
            except Exception as e:
                current_app.logger.error(f"Failed to add user to list: {e}")
                return False

        return True

    def remove_user_from_list(self, username):
        """
        Remove user from vsftpd user list
        Args:
            username: System username to remove
        Returns: True if successful, False otherwise
        """
        users = self.get_user_list()

        if username in users:
            users.remove(username)

            try:
                with open(self.userlist_path, 'w') as f:
                    f.write('\n'.join(users) + '\n')

                current_app.logger.info(f"Removed {username} from FTP user list")
                return True
            except Exception as e:
                current_app.logger.error(f"Failed to remove user from list: {e}")
                return False

        return True

    def get_user_list(self):
        """Get list of allowed FTP users"""
        try:
            if os.path.exists(self.userlist_path):
                with open(self.userlist_path, 'r') as f:
                    return [line.strip() for line in f if line.strip()]
        except Exception as e:
            current_app.logger.error(f"Failed to read user list: {e}")

        return []

    def get_connections(self):
        """Get active FTP connections"""
        try:
            result = subprocess.run(
                ['sudo', 'netstat', '-an'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                # Count connections on port 21
                connections = 0
                for line in result.stdout.split('\n'):
                    if ':21' in line and 'ESTABLISHED' in line:
                        connections += 1
                return connections
        except Exception as e:
            current_app.logger.error(f"Failed to get FTP connections: {e}")

        return 0

    def create_user_directory(self, username, home_dir):
        """
        Create user home directory for FTP access
        Args:
            username: System username
            home_dir: Path to user home directory
        Returns: True if successful, False otherwise
        """
        try:
            # Create directory if not exists
            Path(home_dir).mkdir(parents=True, exist_ok=True)

            # Set permissions (owner: username, group: users, permissions: 750)
            subprocess.run(['sudo', 'chown', f'{username}:users', home_dir], check=True)
            subprocess.run(['sudo', 'chmod', '750', home_dir], check=True)

            current_app.logger.info(f"Created FTP directory for {username}: {home_dir}")
            return True
        except Exception as e:
            current_app.logger.error(f"Failed to create user directory: {e}")
            return False

    def get_service_status(self):
        """Get vsftpd service status"""
        try:
            result = subprocess.run(
                ['sudo', 'systemctl', 'status', 'vsftpd'],
                capture_output=True,
                text=True,
                timeout=10
            )
            return 'active (running)' in result.stdout
        except Exception as e:
            current_app.logger.error(f"Failed to get service status: {e}")
            return False