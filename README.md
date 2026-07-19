# X1011 NAS - Raspberry Pi 网络存储系统

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.2-green.svg)](https://flask.palletsprojects.com/)
[![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%205-red.svg)](https://www.raspberrypi.com/)

基于 Raspberry Pi 5 的轻量级网络附加存储系统，提供 Web 管理界面、Samba 文件共享和 NVMe 存储管理功能。

## ✨ 功能特性

- 🌐 **Web 管理界面** - 基于 Flask 的现代化管理面板
- 💾 **NVMe 存储管理** - 支持多块 NVMe 硬盘监控、挂载、格式化
- 📁 **Samba 文件共享** - Windows/ macOS/Linux 多平台访问
- 📊 **系统监控** - CPU、内存、磁盘实时监控
- 👤 **用户管理** - 多用户认证与权限控制
- 🔒 **审计日志** - 操作记录追踪

## 🖥️ 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    TF 卡 (系统盘)                        │
│  ┌─────────────────────────────────────────────────┐   │
│  │  ~/nas-web/                                     │   │
│  │  ├── app.py          # Flask 主应用             │   │
│  │  ├── models.py       # 数据库模型               │   │
│  │  ├── nas.db          # SQLite 数据库            │   │
│  │  └── ...                                        │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                  NVMe 硬盘阵列 (数据盘)                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐│
│  │ NVMe 0   │  │ NVMe 1   │  │ NVMe 2   │  │ NVMe 3   ││
│  │ 222 GB   │  │ 222 GB   │  │ 222 GB   │  │ 222 GB   ││
│  │ /mnt/    │  │ /mnt/    │  │ /mnt/    │  │ /mnt/    ││
│  │ nvme0    │  │ nvme1    │  │ nvme2    │  │ nvme3    ││
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘│
└─────────────────────────────────────────────────────────┘
```

## 📋 硬件要求

| 组件 | 规格 |
|------|------|
| 主板 | Raspberry Pi 5 |
| 系统 | TF 卡 (≥16GB) |
| 存储 | NVMe SSD × 4 (通过扩展板) |
| 系统 | Debian 12 (ARM64) |

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/wenguangzhao1/X1011-nas.git
cd X1011-nas
```

### 2. 安装依赖

```bash
pip3 install -r requirements.txt
```

### 3. 配置系统依赖

```bash
# 安装系统工具
sudo apt install samba vsftpd smartmontools nvme-cli

# 创建挂载目录
sudo mkdir -p /mnt/nvme{0..3}/shares
```

### 4. 启动服务

```bash
python3 app.py
```

服务将在 `http://0.0.0.0:5000` 启动。

### 5. 访问 Web 界面

- 地址: `http://<你的IP>:5000`
- 默认用户: `admin`
- 默认密码: `admin123`

> ⚠️ **安全提示**: 首次登录后请立即修改默认密码！

## 📁 目录结构

```
nas-web/
├── app.py              # Flask 主应用
├── auth.py             # 用户认证模块
├── config.py           # 配置文件
├── models.py           # 数据库模型
├── nvme_manager.py     # NVMe 管理模块
├── samba_manager.py    # Samba 配置管理
├── ftp_manager.py      # FTP 配置管理
├── system_monitor.py   # 系统监控
├── requirements.txt    # Python 依赖
├── CLAUDE.md           # 项目说明
├── templates/          # HTML 模板
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── nvme.html
│   ├── shares.html
│   ├── users.html
│   └── settings.html
└── static/             # 静态资源
    ├── css/style.css
    └── js/main.js
```

## 🔧 配置说明

### 环境变量

创建 `.env` 文件配置环境变量：

```env
SECRET_KEY=your-secret-key-here
WEB_HOST=0.0.0.0
WEB_PORT=5000
```

### Samba 配置

配置文件位于 `/etc/samba/smb.conf`，通过 Web 界面自动管理。

### NVMe 自动挂载

编辑 `/etc/fstab` 添加自动挂载：

```bash
UUID=<nvme0-uuid> /mnt/nvme0 ext4 defaults,noatime 0 2
UUID=<nvme1-uuid> /mnt/nvme1 ext4 defaults,noatime 0 2
UUID=<nvme2-uuid> /mnt/nvme2 ext4 defaults,noatime 0 2
UUID=<nvme3-uuid> /mnt/nvme3 ext4 defaults,noatime 0 2
```

## 🌐 API 文档

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/system/status` | GET | 获取系统状态 |
| `/api/nvme` | GET | 获取 NVMe 设备信息 |
| `/api/nvme/storage` | GET | 获取存储空间统计 |
| `/api/shares` | GET | 获取共享列表 |
| `/api/users` | GET | 获取用户列表 |

所有 API 需要通过 Flask-Login 认证。

## 🛠️ 开发

### 运行开发服务器

```bash
python3 app.py
```

### 数据库管理

数据库使用 SQLite，位于 `./nas.db`：

```bash
# 重置数据库
rm nas.db
python3 app.py  # 自动重建
```

## 📸 界面预览

### 首页 - NVMe 状态监控
![首页](docs/screenshots/index.png)

### 共享管理
![共享管理](docs/screenshots/shares.png)

### 用户管理
![用户管理](docs/screenshots/users.png)

## 🔒 安全建议

1. **修改默认密码** - 首次部署后立即更改
2. **更改 SECRET_KEY** - 在生产环境使用强密钥
3. **配置防火墙** - 限制访问端口
4. **定期备份** - 备份数据库和配置文件
5. **启用 HTTPS** - 生产环境建议使用 SSL

## 📝 更新日志

### v1.0.0 (2026-07-20)
- ✅ 初始版本发布
- ✅ NVMe 4 盘位支持
- ✅ Samba 文件共享
- ✅ Web 管理界面

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本项目仅供学习和个人使用。

---

**作者**: wenguangzhao1  
**项目地址**: https://github.com/wenguangzhao1/X1011-nas