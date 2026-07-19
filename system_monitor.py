"""
System monitoring module
"""
import os
import subprocess
from datetime import datetime
from flask import current_app
try:
    import psutil
except ImportError:
    psutil = None


class SystemMonitor:
    """System resource monitoring"""

    def __init__(self):
        pass

    def get_disk_usage(self, path='/'):
        """
        Get disk usage information
        Returns: dict with disk usage data
        """
        try:
            if psutil:
                usage = psutil.disk_usage(path)
                return {
                    'path': path,
                    'total': self._bytes_to_gb(usage.total),
                    'used': self._bytes_to_gb(usage.used),
                    'free': self._bytes_to_gb(usage.free),
                    'percent': usage.percent,
                    'status': 'OK' if usage.percent < 90 else 'WARNING' if usage.percent < 95 else 'CRITICAL'
                }
            else:
                # Fallback: use df command
                result = subprocess.run(
                    ['df', '-BG', path],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) >= 2:
                        parts = lines[1].split()
                        return {
                            'path': path,
                            'total': int(parts[1].rstrip('G')),
                            'used': int(parts[2].rstrip('G')),
                            'free': int(parts[3].rstrip('G')),
                            'percent': int(parts[4].rstrip('%')),
                            'status': 'OK'
                        }
        except Exception as e:
            current_app.logger.error(f"Failed to get disk usage: {e}")

        return None

    def get_memory_usage(self):
        """
        Get memory usage information
        Returns: dict with memory usage data
        """
        try:
            if psutil:
                mem = psutil.virtual_memory()
                return {
                    'total': self._bytes_to_gb(mem.total),
                    'available': self._bytes_to_gb(mem.available),
                    'used': self._bytes_to_gb(mem.used),
                    'percent': mem.percent,
                    'status': 'OK' if mem.percent < 80 else 'WARNING'
                }
            else:
                # Fallback: read from /proc/meminfo
                meminfo = {}
                with open('/proc/meminfo', 'r') as f:
                    for line in f:
                        if ':' in line:
                            key, value = line.split(':', 1)
                            meminfo[key.strip()] = int(value.strip().split()[0])

                total_mb = meminfo.get('MemTotal', 0) // 1024
                available_mb = meminfo.get('MemAvailable', meminfo.get('MemFree', 0)) // 1024
                used_mb = total_mb - available_mb
                percent = (used_mb / total_mb * 100) if total_mb > 0 else 0

                return {
                    'total': round(total_mb / 1024, 2),
                    'available': round(available_mb / 1024, 2),
                    'used': round(used_mb / 1024, 2),
                    'percent': round(percent, 1),
                    'status': 'OK' if percent < 80 else 'WARNING'
                }
        except Exception as e:
            current_app.logger.error(f"Failed to get memory usage: {e}")

        return None

    def get_cpu_usage(self):
        """
        Get CPU usage information
        Returns: dict with CPU usage data
        """
        try:
            if psutil:
                cpu_percent = psutil.cpu_percent(interval=1)
                cpu_count = psutil.cpu_count()
                cpu_cores = psutil.cpu_count(logical=False)

                return {
                    'percent': cpu_percent,
                    'count': cpu_count,
                    'cores': cpu_cores,
                    'status': 'OK' if cpu_percent < 70 else 'WARNING' if cpu_percent < 90 else 'CRITICAL'
                }
            else:
                # Fallback: read from /proc/stat
                with open('/proc/stat', 'r') as f:
                    line = f.readline()
                    parts = line.split()
                    if len(parts) >= 5:
                        user, nice, system, idle, iowait = map(int, parts[1:6])
                        total = user + nice + system + idle + iowait
                        used = user + nice + system
                        percent = (used / total * 100) if total > 0 else 0

                        return {
                            'percent': round(percent, 1),
                            'count': os.cpu_count(),
                            'cores': os.cpu_count(),
                            'status': 'OK'
                        }
        except Exception as e:
            current_app.logger.error(f"Failed to get CPU usage: {e}")

        return None

    def get_system_info(self):
        """
        Get system information
        Returns: dict with system info
        """
        try:
            # Get hostname
            hostname = os.uname().nodename

            # Get uptime
            if psutil:
                boot_time = datetime.fromtimestamp(psutil.boot_time())
                uptime = datetime.now() - boot_time
                uptime_str = str(uptime).split('.')[0]  # Remove microseconds
            else:
                with open('/proc/uptime', 'r') as f:
                    uptime_seconds = float(f.readline().split()[0])
                    uptime_str = str(int(uptime_seconds // 3600)) + ' hours'

            # Get OS info
            os_info = 'Unknown'
            try:
                with open('/etc/os-release', 'r') as f:
                    for line in f:
                        if line.startswith('PRETTY_NAME='):
                            os_info = line.split('=')[1].strip().strip('"')
                            break
            except:
                pass

            return {
                'hostname': hostname,
                'os': os_info,
                'uptime': uptime_str,
                'arch': os.uname().machine
            }
        except Exception as e:
            current_app.logger.error(f"Failed to get system info: {e}")

        return None

    def get_network_info(self):
        """
        Get network information
        Returns: dict with network info
        """
        try:
            # Get IP addresses
            ip_addresses = []

            if psutil:
                for interface, addrs in psutil.net_if_addrs().items():
                    for addr in addrs:
                        if addr.family == 2:  # IPv4
                            ip_addresses.append({
                                'interface': interface,
                                'ip': addr.address
                            })
            else:
                # Fallback: use ip command
                result = subprocess.run(
                    ['ip', 'addr', 'show'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    current_interface = None
                    for line in result.stdout.split('\n'):
                        if ': ' in line:
                            current_interface = line.split(':')[1].strip()
                        elif 'inet ' in line and current_interface:
                            ip = line.strip().split()[1].split('/')[0]
                            ip_addresses.append({
                                'interface': current_interface,
                                'ip': ip
                            })

            return {
                'interfaces': ip_addresses
            }
        except Exception as e:
            current_app.logger.error(f"Failed to get network info: {e}")

        return None

    def get_all_metrics(self):
        """
        Get all system metrics
        Returns: dict with all metrics
        """
        return {
            'disk': self.get_disk_usage(),
            'memory': self.get_memory_usage(),
            'cpu': self.get_cpu_usage(),
            'system': self.get_system_info(),
            'network': self.get_network_info(),
            'timestamp': datetime.now().isoformat()
        }

    def _bytes_to_gb(self, bytes_value):
        """Convert bytes to gigabytes"""
        return round(bytes_value / (1024 ** 3), 2)

    def check_service_status(self, service_name):
        """
        Check if a system service is running
        Args:
            service_name: Name of the service (e.g., 'smbd', 'vsftpd')
        Returns: dict with service status
        """
        try:
            result = subprocess.run(
                ['sudo', 'systemctl', 'is-active', service_name],
                capture_output=True,
                text=True,
                timeout=10
            )

            is_active = result.returncode == 0

            return {
                'name': service_name,
                'active': is_active,
                'status': 'running' if is_active else 'stopped'
            }
        except Exception as e:
            current_app.logger.error(f"Failed to check service status: {e}")
            return {
                'name': service_name,
                'active': False,
                'status': 'unknown'
            }