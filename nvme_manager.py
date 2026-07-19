"""
NVMe Storage Manager Module
Manages NVMe SSD devices including health monitoring, temperature, and mount operations
"""
import os
import subprocess
import json
from flask import current_app


class NVMeManager:
    """NVMe device management and monitoring"""

    def __init__(self):
        self.temp_warning = 70  # Temperature warning threshold (Celsius)
        self.temp_critical = 80  # Temperature critical threshold (Celsius)

    def get_nvme_devices(self):
        """
        Get list of all NVMe devices
        Returns: list of device names (e.g., ['nvme0n1', 'nvme1n1'])
        """
        try:
            result = subprocess.run(
                ['lsblk', '-d', '-n', '-o', 'NAME'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                devices = [line.strip() for line in result.stdout.strip().split('\n')
                          if line.strip().startswith('nvme')]
                return devices
        except Exception as e:
            current_app.logger.error(f"Failed to get NVMe devices: {e}")
        return []

    def get_nvme_info(self, device):
        """
        Get detailed information for a single NVMe device
        Args:
            device: device name (e.g., 'nvme0n1')
        Returns: dict with device info
        """
        try:
            # Get basic info from lsblk
            result = subprocess.run(
                ['lsblk', '-b', '-d', '-o', 'NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE', f'/dev/{device}'],
                capture_output=True,
                text=True,
                timeout=10
            )

            info = {
                'device': device,
                'path': f'/dev/{device}',
                'size': 'Unknown',
                'size_bytes': 0,
                'mountpoint': None,
                'fstype': None
            }

            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                # Skip header line
                if len(lines) >= 2:
                    parts = lines[1].split()
                    if len(parts) >= 2:
                        size_bytes = int(parts[1]) if parts[1].isdigit() else 0
                        info['size_bytes'] = size_bytes
                        info['size'] = self._bytes_to_gb(size_bytes)
                        if len(parts) >= 4:
                            info['mountpoint'] = parts[3] if parts[3] else None
                        if len(parts) >= 5:
                            info['fstype'] = parts[4] if parts[4] else None

            # Get SMART info
            smart_info = self.get_nvme_smart(device)
            if smart_info:
                info.update(smart_info)

            return info
        except Exception as e:
            current_app.logger.error(f"Failed to get NVMe info for {device}: {e}")
            return None

    def get_nvme_smart(self, device):
        """
        Get SMART health information for NVMe device
        Args:
            device: device name (e.g., 'nvme0n1')
        Returns: dict with SMART data
        """
        try:
            device_path = f'/dev/{device}'

            result = subprocess.run(
                ['sudo', 'smartctl', '-a', device_path],
                capture_output=True,
                text=True,
                timeout=30
            )

            smart_data = {
                'model': 'Unknown',
                'serial': 'Unknown',
                'temperature': 0,
                'health': 'Unknown',
                'percentage_used': 0,
                'power_cycles': 0,
                'power_on_hours': 0,
                'data_read_gb': 0,
                'data_written_gb': 0
            }

            if result.returncode == 0 or 'SMART/Health Information' in result.stdout:
                output = result.stdout

                # Parse model number
                for line in output.split('\n'):
                    line = line.strip()
                    if 'Model Number:' in line:
                        smart_data['model'] = line.split(':')[1].strip()
                    elif 'Serial Number:' in line:
                        smart_data['serial'] = line.split(':')[1].strip()
                    elif 'Temperature:' in line and 'Celsius' in line:
                        try:
                            smart_data['temperature'] = int(line.split()[1])
                        except:
                            pass
                    elif 'Percentage Used:' in line:
                        try:
                            val = line.split(':')[1].strip().replace('%', '')
                            smart_data['percentage_used'] = int(val)
                        except:
                            pass
                    elif 'Power Cycles:' in line:
                        try:
                            smart_data['power_cycles'] = int(line.split(':')[1].strip().replace(',', ''))
                        except:
                            pass
                    elif 'Power On Hours:' in line:
                        try:
                            smart_data['power_on_hours'] = int(line.split(':')[1].strip().split('.')[0])
                        except:
                            pass
                    elif 'Data Units Read:' in line:
                        try:
                            val = line.split(':')[1].strip().split()[0].replace(',', '')
                            smart_data['data_read_gb'] = int(val) * 512 // 1024 // 1024
                        except:
                            pass
                    elif 'Data Units Written:' in line:
                        try:
                            val = line.split(':')[1].strip().split()[0].replace(',', '')
                            smart_data['data_written_gb'] = int(val) * 512 // 1024 // 1024
                        except:
                            pass

                # Check health status
                if 'SMART overall-health self-assessment test result:' in output:
                    if 'PASSED' in output:
                        smart_data['health'] = 'PASSED'
                    else:
                        smart_data['health'] = 'FAILED'
                else:
                    smart_data['health'] = 'PASSED'

            return smart_data
        except Exception as e:
            current_app.logger.error(f"Failed to get SMART data for {device}: {e}")
            return None

    def get_nvme_all(self):
        """
        Get information for all NVMe devices
        Returns: list of dicts with device info
        """
        devices = self.get_nvme_devices()
        result = []
        for device in devices:
            info = self.get_nvme_info(device)
            if info:
                result.append(info)
        return result

    def get_temperature_summary(self):
        """
        Get temperature summary for all NVMe devices
        Returns: dict with temperature stats
        """
        devices = self.get_nvme_all()
        temps = [d.get('temperature', 0) for d in devices if d.get('temperature')]

        return {
            'devices': len(devices),
            'max_temp': max(temps) if temps else 0,
            'min_temp': min(temps) if temps else 0,
            'avg_temp': round(sum(temps) / len(temps), 1) if temps else 0,
            'warning_count': len([t for t in temps if t >= self.temp_warning]),
            'critical_count': len([t for t in temps if t >= self.temp_critical]),
            'status': 'OK' if not any(t >= self.temp_warning for t in temps)
                      else 'WARNING' if not any(t >= self.temp_critical for t in temps)
                      else 'CRITICAL'
        }

    def get_health_summary(self):
        """
        Get health summary for all NVMe devices
        Returns: dict with health stats
        """
        devices = self.get_nvme_all()
        passed = len([d for d in devices if d.get('health') == 'PASSED'])

        return {
            'total': len(devices),
            'passed': passed,
            'failed': len(devices) - passed,
            'status': 'OK' if passed == len(devices) else 'WARNING'
        }

    def mount_nvme(self, device, mount_point):
        """
        Mount an NVMe partition
        Args:
            device: device partition (e.g., 'nvme0n1p1')
            mount_point: mount point path
        Returns: (success, message)
        """
        try:
            device_path = f'/dev/{device}'

            # Check if device exists
            if not os.path.exists(device_path):
                return False, f"Device {device_path} not found"

            # Create mount point if not exists
            if not os.path.exists(mount_point):
                subprocess.run(['sudo', 'mkdir', '-p', mount_point], check=True)

            # Check if already mounted
            result = subprocess.run(
                ['mountpoint', '-q', mount_point],
                capture_output=True
            )
            if result.returncode == 0:
                return False, f"{mount_point} is already mounted"

            # Check if device has filesystem
            result = subprocess.run(
                ['lsblk', '-no', 'FSTYPE', device_path],
                capture_output=True,
                text=True
            )
            fstype = result.stdout.strip()

            if not fstype:
                # Need to format first
                return False, f"Device {device} has no filesystem. Please format it first."

            # Mount the device
            result = subprocess.run(
                ['sudo', 'mount', device_path, mount_point],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                # Set permissions
                subprocess.run(['sudo', 'chmod', '777', mount_point])
                return True, f"Successfully mounted {device} at {mount_point}"
            else:
                return False, f"Mount failed: {result.stderr}"

        except Exception as e:
            return False, f"Mount error: {str(e)}"

    def unmount_nvme(self, mount_point):
        """
        Unmount an NVMe partition
        Args:
            mount_point: mount point path
        Returns: (success, message)
        """
        try:
            # Check if mounted
            result = subprocess.run(
                ['mountpoint', '-q', mount_point],
                capture_output=True
            )
            if result.returncode != 0:
                return False, f"{mount_point} is not mounted"

            # Unmount
            result = subprocess.run(
                ['sudo', 'umount', mount_point],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return True, f"Successfully unmounted {mount_point}"
            else:
                return False, f"Unmount failed: {result.stderr}"

        except Exception as e:
            return False, f"Unmount error: {str(e)}"

    def format_nvme(self, device, fstype='ext4'):
        """
        Format an NVMe partition with filesystem
        Args:
            device: device partition (e.g., 'nvme0n1p1')
            fstype: filesystem type (default: ext4)
        Returns: (success, message)
        """
        try:
            device_path = f'/dev/{device}'

            if not os.path.exists(device_path):
                return False, f"Device {device_path} not found"

            # Format with chosen filesystem
            if fstype == 'ext4':
                cmd = ['sudo', 'mkfs.ext4', '-F', device_path]
            elif fstype == 'xfs':
                cmd = ['sudo', 'mkfs.xfs', '-f', device_path]
            elif fstype == 'ntfs':
                cmd = ['sudo', 'mkfs.ntfs', '-f', device_path]
            else:
                return False, f"Unsupported filesystem: {fstype}"

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                return True, f"Successfully formatted {device} as {fstype}"
            else:
                return False, f"Format failed: {result.stderr}"

        except Exception as e:
            return False, f"Format error: {str(e)}"

    def get_partitions(self, device):
        """
        Get partitions for an NVMe device
        Args:
            device: device name (e.g., 'nvme0n1')
        Returns: list of partition info
        """
        try:
            result = subprocess.run(
                ['lsblk', '-n', '-o', 'NAME,SIZE,MOUNTPOINT,FSTYPE', f'/dev/{device}'],
                capture_output=True,
                text=True,
                timeout=10
            )

            partitions = []
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n')[1:]:
                    parts = line.strip().split()
                    if len(parts) >= 4:
                        partitions.append({
                            'name': parts[0],
                            'size': parts[1],
                            'mountpoint': parts[2] if parts[2] != 'None' else None,
                            'fstype': parts[3] if len(parts) > 3 else None
                        })
            return partitions
        except Exception as e:
            current_app.logger.error(f"Failed to get partitions for {device}: {e}")
            return []

    def get_storage_info(self):
        """
        Get storage space info for all NVMe drives
        Returns: dict with storage info
        """
        import shutil

        disks = []
        for i in range(4):
            mount_point = f'/mnt/nvme{i}'
            if os.path.ismount(mount_point):
                try:
                    usage = shutil.disk_usage(mount_point)
                    total_gb = round(usage.total / (1024**3), 1)
                    used_gb = round(usage.used / (1024**3), 1)
                    available_gb = round(usage.free / (1024**3), 1)
                    percent = round(usage.used / usage.total * 100, 1)

                    disks.append({
                        'disk': f'nvme{i}',
                        'mount_point': mount_point,
                        'share_name': 'PiShare' if i == 0 else f'Share-{i}',
                        'total_gb': total_gb,
                        'used_gb': used_gb,
                        'available_gb': available_gb,
                        'percent': percent
                    })
                except Exception as e:
                    pass

        return {'disks': disks}

    def _bytes_to_gb(self, bytes_value):
        """Convert bytes to gigabytes"""
        if bytes_value == 0:
            return "0 GB"
        return f"{round(bytes_value / (1024 ** 3), 1)} GB"