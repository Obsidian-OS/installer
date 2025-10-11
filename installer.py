#!/usr/bin/env python3
import sys
import os
import subprocess
import time
import re
from pathlib import Path
script_dir = os.path.dirname(os.path.abspath(__file__))
from PySide6.QtWidgets import (QApplication, QMainWindow, QStackedWidget, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel, QListWidget, QRadioButton, QButtonGroup, QProgressBar, QTextEdit, QFrame, QSpacerItem, QSizePolicy, QListWidgetItem, QSpinBox, QFormLayout, QGroupBox, QMessageBox, QComboBox, QStyle, QDialog, QLineEdit)
from PySide6.QtCore import Qt, QThread, QTimer, Signal, QProcess
from PySide6.QtGui import QFont, QPalette, QPixmap, QIcon, QTextCursor
from PySide6.QtWidgets import QGraphicsDropShadowEffect
import pty

test_mode = "--test" in sys.argv

class InstallWorker(QThread):
    progress_updated = Signal(str)
    finished = Signal(bool, str)
    chroot_entered = Signal()
    def __init__(self, disk, image, rootfs_size, esp_size, etc_size, var_size, dual_boot, filesystem_type, locale, timezone, keyboard):
        super().__init__()
        self.disk = disk
        self.image = image
        self.rootfs_size = rootfs_size
        self.esp_size = esp_size
        self.etc_size = etc_size
        self.var_size = var_size
        self.dual_boot = dual_boot
        self.filesystem_type = filesystem_type
        self.locale = locale
        self.timezone = timezone
        self.keyboard = keyboard
        self.process = None
        self.master_fd = None
        self.installation_succeeded_by_output = False
        self.installation_failed_by_output = False
        self.in_chroot = False

    def run(self):
        try:
            if test_mode:
                dummy_cmd = [
                    'sh', '-c',
                    'echo "Test running..."; sleep 1; '
                    'echo "Partitioning disk..."; sleep 1; '
                    'echo "Installing system image..."; sleep 2; '
                    'echo "Configuring bootloader..."; sleep 1; '
                    'read -p "Do you want to proceed (y/N): " answer; echo "User answered: $answer"; '
                    'sleep 5; '
                    'echo "Installation complete"'
                ]
                self.progress_updated.emit("Starting installation...")
            else:
                cmd = [
                    'sudo', '-S', 'obsidianctl', 'install',
                    self.disk,
                    self.image,
                    '--rootfs-size', str(self.rootfs_size),
                    '--esp-size', str(self.esp_size),
                    '--etc-size', str(self.etc_size),
                    '--var-size', str(self.var_size)
                ]

                if self.dual_boot:
                    cmd.append('--dual-boot')

                if self.filesystem_type == "f2fs":
                    cmd.append('--use-f2fs')

                self.progress_updated.emit("Starting installation...")
                dummy_cmd = cmd

            master_fd, slave_fd = pty.openpty()
            self.master_fd = master_fd
            self.process = subprocess.Popen(
                dummy_cmd,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                preexec_fn=os.setsid,
                text=False,
                bufsize=0
            )
            os.close(slave_fd)
            import select
            last_output_time = time.time()
            while True:
                if self.process.poll() is not None:
                    try:
                        remaining_output = os.read(self.master_fd, 4096).decode(errors='ignore')
                        if remaining_output:
                            for line in remaining_output.splitlines():
                                if line.strip():
                                    self.progress_updated.emit(line)
                                    if "installation complete" in line.lower():
                                        self.installation_succeeded_by_output = True
                                    elif "error:" in line.lower() or "failed" in line.lower():
                                        self.installation_failed_by_output = True
                    except OSError:
                        pass
                    break

                ready, _, _ = select.select([self.master_fd], [], [], 0.1)
                if ready:
                    try:
                        output = os.read(self.master_fd, 1024).decode(errors='ignore')
                        if output:
                            last_output_time = time.time()
                            for line in output.splitlines():
                                if line.strip():
                                    self.progress_updated.emit(line)
                                    if "installation complete" in line.lower():
                                        self.installation_succeeded_by_output = True
                                    elif "error:" in line.lower() or "failed" in line.lower():
                                        self.installation_failed_by_output = True
                    except OSError:
                        break
            os.close(self.master_fd)
            self.master_fd = None
            if self.installation_succeeded_by_output:
                self.progress_updated.emit("Installation completed successfully!")
                self.finished.emit(True, "Installation completed successfully")
            elif self.installation_failed_by_output:
                self.finished.emit(False, "Installation failed based on output messages.")
            else:
                return_code = self.process.returncode
                if return_code == 0:
                    self.progress_updated.emit("Installation completed successfully!")
                    self.finished.emit(True, "Installation completed successfully")
                elif return_code is not None:
                    error_msg = f"Installation failed with return code {return_code}"
                    self.progress_updated.emit(error_msg)
                    self.finished.emit(False, error_msg)
                else:
                    error_msg = "Installation status uncertain: Process terminated without clear exit code or output message."
                    self.progress_updated.emit(error_msg)
                    self.finished.emit(False, error_msg)

        except FileNotFoundError:
            error_msg = "Error: 'obsidianctl' command not found. Please ensure ObsidianOS tools are installed."
            self.progress_updated.emit(error_msg)
            self.finished.emit(False, error_msg)
        except Exception as e:
            error_msg = f"Installation error: {str(e)}"
            self.progress_updated.emit(error_msg)
            self.finished.emit(False, error_msg)
        finally:
            if self.master_fd is not None:
                try:
                    os.close(self.master_fd)
                except OSError:
                    pass
                self.master_fd = None



    def send_input(self, text):
        if self.master_fd is not None and self.process and self.process.poll() is None:
            try:
                os.write(self.master_fd, (text + '\n').encode())
            except OSError:
                pass

    def send_configs(self):
        commands = [
            f"locale-gen {self.locale}",
            f"localectl set-locale LANG={self.locale}",
            f"timedatectl set-timezone {self.timezone}",
            f"localectl set-keymap {self.keyboard}"
        ]
        for cmd in commands:
            self.send_input(cmd)


class WelcomePage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(30)
        title = QLabel("ObsidianOS")
        title.setAlignment(Qt.AlignCenter)
        title.setObjectName("welcome-title")
        subtitle = QLabel("The GNU/Linux distribution with A/B Partitioning.")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setObjectName("welcome-subtitle")
        description = QLabel("Let's start the installation now!" if not test_mode else "Running in test mode!!")
        description.setAlignment(Qt.AlignCenter)
        description.setWordWrap(True)
        logo_label = QLabel()
        pixmap = QPixmap(os.path.join(script_dir, "logo.svg"))
        if pixmap.isNull():
            pixmap = QPixmap(os.path.join("/usr/share/pixmaps", "obsidianos.png"))
        if not pixmap.isNull():
            max_logo_width = 200
            scaled_pixmap = pixmap.scaled(max_logo_width, pixmap.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
            logo_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(logo_label)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(description)
        self.setLayout(layout)

class DiskSelectionPage(QWidget):
    def __init__(self):
        super().__init__()
        self.selected_disk = None
        self.init_ui()
        self.scan_disks()

    def init_ui(self):
        main_frame = QFrame()
        main_frame.setFrameStyle(QFrame.NoFrame)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setOffset(0, 3)
        shadow.setColor(Qt.black)
        main_frame.setGraphicsEffect(shadow)
        layout = QVBoxLayout(main_frame)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        title = QLabel("Select Installation Disk")
        title.setObjectName("page-title")
        title.setAlignment(Qt.AlignCenter)
        self.disk_list = QListWidget()
        self.disk_list.itemClicked.connect(self.on_disk_selected)
        self.disk_list.setObjectName("disk-list")
        warning_frame = QFrame()
        warning_layout = QHBoxLayout(warning_frame)
        warning_layout.setContentsMargins(10, 10, 10, 10)
        warning_icon = QLabel()
        warning_icon.setPixmap(self.style().standardIcon(QStyle.SP_MessageBoxWarning).pixmap(24, 24))
        warning = QLabel("Warning: All data on the selected disk will be erased!")
        warning.setObjectName("warning-label")
        warning_layout.addWidget(warning_icon)
        warning_layout.addWidget(warning, 1)
        layout.addWidget(title)
        layout.addWidget(self.disk_list)
        layout.addWidget(warning_frame)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(main_frame)
        self.setLayout(main_layout)

    def scan_disks(self):
        if test_mode:
            dummy_disks = [
                ("sda", "500G", "Test SSD"),
                ("sdb", "1T", "Test HDD"),
                ("nvme0n1", "256G", "Test NVMe")
            ]
            for name, size, model in dummy_disks:
                item_text = f"/dev/{name} - {size} - {model}"
                item = QListWidgetItem(item_text)
                item.setIcon(QIcon.fromTheme("drive-harddisk"))
                item.setData(Qt.UserRole, f"/dev/{name}")
                self.disk_list.addItem(item)
            return

        try:
            result = subprocess.run(['lsblk', '-d', '-n', '-o', 'NAME,SIZE,MODEL'],
                                  capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line and not line.startswith('loop'):
                    parts = line.split(None, 2)
                    if len(parts) >= 2:
                        name = parts[0]
                        size = parts[1]
                        model = parts[2] if len(parts) > 2 else "Unknown"
                        item_text = f"/dev/{name} - {size} - {model}"
                        item = QListWidgetItem(item_text)
                        item.setIcon(QIcon.fromTheme("drive-harddisk"))
                        item.setData(Qt.UserRole, f"/dev/{name}")
                        self.disk_list.addItem(item)
        except:
            item = QListWidgetItem("ERROR DETECTING DISKS")
            item.setIcon(QIcon.fromTheme("dialog-error"))
            item.setData(Qt.UserRole, "ERROR")
            self.disk_list.addItem(item)

    def on_disk_selected(self, item):
        self.selected_disk = item.data(Qt.UserRole)

    def get_selected_disk(self):
        return self.selected_disk

class DualBootPage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        main_frame = QFrame()
        main_frame.setFrameStyle(QFrame.NoFrame)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 4)
        shadow.setColor(Qt.black)
        main_frame.setGraphicsEffect(shadow)
        layout = QVBoxLayout(main_frame)
        layout.setSpacing(25)
        layout.setContentsMargins(30, 30, 30, 30)
        title = QLabel("Dual Boot Configuration")
        title.setObjectName("page-title")
        title.setAlignment(Qt.AlignCenter)
        description = QLabel("Choose how you want to install ObsidianOS:")
        description.setAlignment(Qt.AlignCenter)
        description.setWordWrap(True)
        options_layout = QVBoxLayout()
        options_layout.setSpacing(15)
        self.button_group = QButtonGroup()
        erase_layout = QHBoxLayout()
        erase_icon = QLabel()
        erase_icon.setPixmap(self.style().standardIcon(QStyle.SP_MessageBoxCritical).pixmap(32, 32))
        self.erase_option = QRadioButton("Erase entire disk and install ObsidianOS")
        self.erase_option.setChecked(True)
        erase_layout.addWidget(erase_icon)
        erase_layout.addWidget(self.erase_option, 1)
        self.button_group.addButton(self.erase_option)
        alongside_layout = QHBoxLayout()
        alongside_icon = QLabel()
        alongside_icon.setPixmap(self.style().standardIcon(QStyle.SP_MessageBoxInformation).pixmap(32, 32))
        self.alongside_option = QRadioButton("Install ObsidianOS alongside existing OS")
        alongside_layout.addWidget(alongside_icon)
        alongside_layout.addWidget(self.alongside_option, 1)
        self.button_group.addButton(self.alongside_option)
        options_layout.addLayout(erase_layout)
        options_layout.addLayout(alongside_layout)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addLayout(options_layout)
        layout.addStretch()
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(main_frame)
        self.setLayout(main_layout)

    def get_selected_option(self):
        if self.erase_option.isChecked():
            return "erase"
        elif self.alongside_option.isChecked():
            return "alongside"
        else:
            return "erase"

class AdvancedOptionsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        main_frame = QFrame()
        main_frame.setFrameStyle(QFrame.NoFrame)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 4)
        shadow.setColor(Qt.black)
        main_frame.setGraphicsEffect(shadow)
        layout = QVBoxLayout(main_frame)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        title = QLabel("Advanced Options")
        title.setObjectName("page-title")
        title.setAlignment(Qt.AlignCenter)
        description = QLabel("Configure partition sizes for your ObsidianOS installation:")
        description.setAlignment(Qt.AlignCenter)
        description.setWordWrap(True)
        group_box = QGroupBox("Partition Configuration")
        group_box.setObjectName("advanced-group")
        form_layout = QFormLayout()
        form_layout.setVerticalSpacing(15)
        form_layout.setHorizontalSpacing(10)
        self.rootfs_size = QSpinBox()
        self.rootfs_size.setRange(1, 9999)
        self.rootfs_size.setValue(6)
        self.rootfs_size.setSuffix("G")
        form_layout.addRow("Root filesystem size:", self.rootfs_size)
        self.esp_size = QSpinBox()
        self.esp_size.setRange(100, 2048)
        self.esp_size.setValue(512)
        self.esp_size.setSuffix("M")
        form_layout.addRow("ESP (EFI System Partition) size:", self.esp_size)
        self.etc_ab_size = QSpinBox()
        self.etc_ab_size.setRange(1, 9999)
        self.etc_ab_size.setValue(5)
        self.etc_ab_size.setSuffix("G")
        form_layout.addRow("etc_ab partition size:", self.etc_ab_size)
        self.var_ab_size = QSpinBox()
        self.var_ab_size.setRange(1, 9999)
        self.var_ab_size.setValue(5)
        self.var_ab_size.setSuffix("G")
        form_layout.addRow("var_ab partition size:", self.var_ab_size)
        self.filesystem_type_combo = QComboBox()
        self.filesystem_type_combo.addItem("ext4")
        self.filesystem_type_combo.addItem("f2fs")
        form_layout.addRow("Filesystem Type:", self.filesystem_type_combo)
        group_box.setLayout(form_layout)
        info_frame = QFrame()
        info_layout = QHBoxLayout(info_frame)
        info_layout.setContentsMargins(10, 10, 10, 10)
        info_icon = QLabel()
        info_icon.setPixmap(self.style().standardIcon(QStyle.SP_MessageBoxInformation).pixmap(24, 24))
        info_label = QLabel("The A/B system requires duplicate partitions for safe updates and rollback capabilities.")
        info_label.setWordWrap(True)
        info_label.setObjectName("info-label")
        info_layout.addWidget(info_icon)
        info_layout.addWidget(info_label, 1)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(group_box)
        layout.addWidget(info_frame)
        layout.addStretch()
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(main_frame)
        self.setLayout(main_layout)

    def get_partition_config(self):
        return {
            'rootfs_size': f"{self.rootfs_size.value()}G",
            'esp_size': f"{self.esp_size.value()}M",
            'etc_ab_size': f"{self.etc_ab_size.value()}G",
            'var_ab_size': f"{self.var_ab_size.value()}G"
        }

    def get_filesystem_type(self):
        return self.filesystem_type_combo.currentText()

class SystemImagePage(QWidget):
    def __init__(self):
        super().__init__()
        self.selected_image = "/etc/system.sfs"
        self.init_ui()
        self.scan_images()

    def init_ui(self):
        main_frame = QFrame()
        main_frame.setFrameStyle(QFrame.NoFrame)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setOffset(0, 3)
        shadow.setColor(Qt.black)
        main_frame.setGraphicsEffect(shadow)
        layout = QVBoxLayout(main_frame)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        title = QLabel("Select System Image")
        title.setObjectName("page-title")
        title.setAlignment(Qt.AlignCenter)
        self.image_list = QListWidget()
        self.image_list.itemClicked.connect(self.on_image_selected)
        self.image_list.setObjectName("image-list")
        layout.addWidget(title)
        layout.addWidget(self.image_list)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(main_frame)
        self.setLayout(main_layout)

    def scan_images(self):
        default_item = QListWidgetItem("Default System Image")
        default_item.setIcon(QIcon.fromTheme("package"))
        default_item.setData(Qt.UserRole, "/etc/system.sfs")
        self.image_list.addItem(default_item)
        self.image_list.setCurrentItem(default_item)
        preconf_path = Path("/usr/preconf")
        if preconf_path.exists():
            for file in preconf_path.glob("*.mkobsfs"):
                item = QListWidgetItem(file.stem)
                item.setIcon(QIcon.fromTheme("system-run"))
                item.setData(Qt.UserRole, str(file))
                self.image_list.addItem(item)

        home_path = Path.home()
        for ext in ["*.mkobsfs", "*.sfs"]:
            for file in home_path.glob(ext):
                icon_name = "folder" if ext == "*.mkobsfs" else "media-optical"
                item = QListWidgetItem(file.name)
                item.setIcon(QIcon.fromTheme(icon_name))
                item.setData(Qt.UserRole, str(file))
                self.image_list.addItem(item)

    def on_image_selected(self, item):
        self.selected_image = item.data(Qt.UserRole)

    def get_selected_image(self):
        return self.selected_image

class LocalePage(QWidget):
    def __init__(self):
        super().__init__()
        self.selected_locale = "en_US.UTF-8"
        self.init_ui()

    def init_ui(self):
        main_frame = QFrame()
        main_frame.setFrameStyle(QFrame.NoFrame)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setOffset(0, 3)
        shadow.setColor(Qt.black)
        main_frame.setGraphicsEffect(shadow)
        layout = QVBoxLayout(main_frame)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        title = QLabel("Select Locale")
        title.setObjectName("page-title")
        title.setAlignment(Qt.AlignCenter)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search locales...")
        self.search_edit.textChanged.connect(self.filter_locales)
        self.search_edit.setObjectName("search-edit")
        self.locale_list = QListWidget()
        self.locale_list.itemClicked.connect(self.on_locale_selected)
        self.locale_list.setObjectName("locale-list")
        try:
            result = subprocess.run(['ls', '/usr/share/locale'], capture_output=True, text=True)
            locales = result.stdout.strip().split('\n')
        except:
            locales = ["en_US.UTF-8"]
        for loc in locales:
            if loc.strip():
                item = QListWidgetItem(loc)
                item.setIcon(QIcon.fromTheme("preferences-desktop-locale"))
                self.locale_list.addItem(item)
        if self.locale_list.count() > 0:
            self.locale_list.setCurrentRow(0)
        layout.addWidget(title)
        layout.addWidget(self.search_edit)
        layout.addWidget(self.locale_list)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(main_frame)
        self.setLayout(main_layout)

    def filter_locales(self):
        text = self.search_edit.text().lower()
        for i in range(self.locale_list.count()):
            item = self.locale_list.item(i)
            item.setHidden(text not in item.text().lower())

    def on_locale_selected(self, item):
        self.selected_locale = item.text()

    def get_selected_locale(self):
        return self.selected_locale

class TimezonePage(QWidget):
    def __init__(self):
        super().__init__()
        self.selected_timezone = "UTC"
        self.init_ui()

    def init_ui(self):
        main_frame = QFrame()
        main_frame.setFrameStyle(QFrame.NoFrame)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setOffset(0, 3)
        shadow.setColor(Qt.black)
        main_frame.setGraphicsEffect(shadow)
        layout = QVBoxLayout(main_frame)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        title = QLabel("Select Timezone")
        title.setObjectName("page-title")
        title.setAlignment(Qt.AlignCenter)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search timezones...")
        self.search_edit.textChanged.connect(self.filter_timezones)
        self.search_edit.setObjectName("search-edit")
        self.tz_list = QListWidget()
        self.tz_list.itemClicked.connect(self.on_tz_selected)
        self.tz_list.setObjectName("timezone-list")
        try:
            result = subprocess.run(['timedatectl', 'list-timezones'], capture_output=True, text=True)
            timezones = result.stdout.strip().split('\n')
        except:
            timezones = ["UTC"]
        for tz in timezones:
            if tz.strip():
                item = QListWidgetItem(tz)
                item.setIcon(QIcon.fromTheme("preferences-system-time"))
                self.tz_list.addItem(item)
        if self.tz_list.count() > 0:
            self.tz_list.setCurrentRow(0)
        layout.addWidget(title)
        layout.addWidget(self.search_edit)
        layout.addWidget(self.tz_list)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(main_frame)
        self.setLayout(main_layout)

    def filter_timezones(self):
        text = self.search_edit.text().lower()
        for i in range(self.tz_list.count()):
            item = self.tz_list.item(i)
            item.setHidden(text not in item.text().lower())

    def on_tz_selected(self, tz):
        self.selected_timezone = tz.text()

    def get_selected_timezone(self):
        return self.selected_timezone

class KeyboardPage(QWidget):
    def __init__(self):
        super().__init__()
        self.selected_keyboard = "us"
        self.init_ui()

    def init_ui(self):
        main_frame = QFrame()
        main_frame.setFrameStyle(QFrame.NoFrame)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setOffset(0, 3)
        shadow.setColor(Qt.black)
        main_frame.setGraphicsEffect(shadow)
        layout = QVBoxLayout(main_frame)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        title = QLabel("Select Keyboard Layout")
        title.setObjectName("page-title")
        title.setAlignment(Qt.AlignCenter)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search keyboard layouts...")
        self.search_edit.textChanged.connect(self.filter_keyboards)
        self.search_edit.setObjectName("search-edit")
        self.kb_list = QListWidget()
        self.kb_list.itemClicked.connect(self.on_kb_selected)
        self.kb_list.setObjectName("keyboard-list")
        try:
            result = subprocess.run(['localectl', 'list-keymaps'], capture_output=True, text=True)
            keyboards = result.stdout.strip().split('\n')
        except:
            keyboards = ["us", "ar", "ru"]
        for kb in keyboards:
            if kb.strip():
                item = QListWidgetItem(kb)
                item.setIcon(QIcon.fromTheme("input-keyboard"))
                self.kb_list.addItem(item)
        if self.kb_list.count() > 0:
            self.kb_list.setCurrentRow(0)
        layout.addWidget(title)
        layout.addWidget(self.search_edit)
        layout.addWidget(self.kb_list)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(main_frame)
        self.setLayout(main_layout)

    def filter_keyboards(self):
        text = self.search_edit.text().lower()
        for i in range(self.kb_list.count()):
            item = self.kb_list.item(i)
            item.setHidden(text not in item.text().lower())

    def on_kb_selected(self, item):
        self.selected_keyboard = item.text()

    def get_selected_keyboard(self):
        return self.selected_keyboard

class SummaryPage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        main_frame = QFrame()
        main_frame.setFrameStyle(QFrame.NoFrame)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 4)
        shadow.setColor(Qt.black)
        main_frame.setGraphicsEffect(shadow)
        layout = QVBoxLayout(main_frame)
        layout.setSpacing(25)
        layout.setContentsMargins(30, 30, 30, 30)
        title = QLabel("Installation Summary")
        title.setObjectName("page-title")
        title.setAlignment(Qt.AlignCenter)
        summary_frame = QFrame()
        summary_frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        summary_layout = QVBoxLayout(summary_frame)
        summary_layout.setContentsMargins(20, 20, 20, 20)
        self.summary_text = QLabel()
        self.summary_text.setWordWrap(True)
        summary_layout.addWidget(self.summary_text)
        warning_frame = QFrame()
        warning_layout = QHBoxLayout(warning_frame)
        warning_layout.setContentsMargins(10, 10, 10, 10)
        warning_icon = QLabel()
        warning_icon.setPixmap(self.style().standardIcon(QStyle.SP_MessageBoxWarning).pixmap(24, 24))
        warning = QLabel("Warning: Click 'Install' to begin the installation process. This cannot be undone!")
        warning.setObjectName("warning-label")
        warning_layout.addWidget(warning_icon)
        warning_layout.addWidget(warning, 1)
        layout.addWidget(title)
        layout.addWidget(summary_frame)
        layout.addWidget(warning_frame)
        layout.addStretch()
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(main_frame)
        self.setLayout(main_layout)

    def update_summary(self, disk, boot_option, partition_config, image, locale, timezone, keyboard):
        summary = f"""<b>Installation Target:</b> {disk or 'Not selected'}<br><br>
<b>Boot Configuration:</b> {boot_option.replace('_', ' ').title()}<br><br>
<b>System Image:</b> {image or 'Default'}<br><br>
<b>Locale:</b> {locale}<br><br>
<b>Timezone:</b> {timezone}<br><br>
<b>Keyboard Layout:</b> {keyboard}<br><br>
<b>Partition Configuration:</b><br>
• ESP: {partition_config['esp_size']}<br>
• Root filesystem: {partition_config['rootfs_size']} (A/B)<br>
• etc_ab: {partition_config['etc_ab_size']} (A/B)<br>
• var_ab: {partition_config['var_ab_size']} (A/B)<br>"""

        self.summary_text.setText(summary)

class InstallationPage(QWidget):
    def __init__(self):
        super().__init__()
        self.install_worker = None
        self.chroot_config_pending = False
        self.selected_locale = None
        self.selected_timezone = None
        self.selected_keyboard = None
        self.init_ui()

    def init_ui(self):
        main_frame = QFrame()
        main_frame.setFrameStyle(QFrame.NoFrame)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 4)
        shadow.setColor(Qt.black)
        main_frame.setGraphicsEffect(shadow)
        layout = QVBoxLayout(main_frame)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        title = QLabel("Installing ObsidianOS")
        title.setObjectName("page-title")
        title.setAlignment(Qt.AlignCenter)
        self.status_label = QLabel("Preparing installation...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Monospace", 10))
        self.log_text.setObjectName("log-text")
        self.input_area = QWidget()
        self.input_area.setObjectName("input-area")
        input_layout = QVBoxLayout(self.input_area)
        self.question_label = QLabel()
        self.question_label.hide()
        input_layout.addWidget(self.question_label)
        button_layout = QHBoxLayout()
        self.yes_button = QPushButton("Yes")
        self.no_button = QPushButton("No")
        self.yes_button.hide()
        self.no_button.hide()
        button_layout.addWidget(self.yes_button)
        button_layout.addWidget(self.no_button)
        input_layout.addLayout(button_layout)
        self.input_field = QTextEdit()
        self.input_field.setMaximumHeight(30)
        self.send_button = QPushButton()
        self.send_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        self.send_button.clicked.connect(self.send_input)
        text_layout = QHBoxLayout()
        text_layout.addWidget(self.input_field)
        text_layout.addWidget(self.send_button)
        input_layout.addLayout(text_layout)
        layout.addWidget(title)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.log_text)
        layout.addWidget(self.input_area)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(main_frame)
        self.setLayout(main_layout)
        self.yes_button.clicked.connect(lambda: self.send_y_n('y'))
        self.no_button.clicked.connect(lambda: self.send_y_n('n'))
        self.is_y_n_prompt_active = False

    def send_input(self):
        if self.is_y_n_prompt_active:
            return
        if self.install_worker:
            text = self.input_field.toPlainText().strip()
            if text:
                self.install_worker.send_input(text)
                self.log_text.append(f"--> {text}")
                self.input_field.clear()

    def send_y_n(self, choice):
        if self.install_worker:
            self.install_worker.send_input(choice)
            self.log_text.append(f"--> {choice}")
            self.question_label.hide()
            self.yes_button.hide()
            self.no_button.hide()
            self.input_field.show()
            self.send_button.show()
            self.is_y_n_prompt_active = False
            self.input_field.clear()

    def start_installation(self, disk, image, partition_config, dual_boot, filesystem_type, locale, timezone, keyboard):
        self.status_label.setText("Starting installation...")
        self.log_text.clear()
        self.selected_locale = locale
        self.selected_timezone = timezone
        self.selected_keyboard = keyboard
        self.install_worker = InstallWorker(
            disk, image,
            partition_config['rootfs_size'],
            partition_config['esp_size'],
            partition_config['etc_ab_size'],
            partition_config['var_ab_size'],
            dual_boot,
            filesystem_type,
            locale, timezone, keyboard
        )

        self.install_worker.progress_updated.connect(self.update_progress)
        self.install_worker.finished.connect(self.installation_finished)
        self.install_worker.chroot_entered.connect(self.on_chroot_entered)
        self.install_worker.start()

    def on_chroot_entered(self):
        reply = QMessageBox.question(self, "Chroot",
                                   "You are now in chroot. Do you still want to be in chroot?",
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.Yes)
        if reply == QMessageBox.No:
            self.install_worker.send_input('exit')

    def update_progress(self, message):
        self.status_label.setText("Installation in progress...")
        if "Do you want to chroot into slot 'a' to make changes before copying it to slot B? (y/N):" in message:
            self.install_worker.send_input('y')
            self.install_worker.send_configs()
            self.install_worker.chroot_entered.emit()
        elif re.match(r".*\([yY]/[nN]\):\s*$", message):
            match = re.match(r"(.*)\([yY]/[nN]\):\s*$", message)
            if match:
                question = match.group(1).strip()
                self.question_label.setText(question)
                self.question_label.show()
                self.yes_button.show()
                self.no_button.show()
                self.input_field.hide()
                self.send_button.hide()
                self.is_y_n_prompt_active = True
        self.log_text.append(message)
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)

    def installation_finished(self, success, message):
        if success:
            self.status_label.setText("Installation completed successfully!")
            self.progress_bar.setRange(0, 1)
            self.progress_bar.setValue(1)
        else:
            self.status_label.setText(f"Installation failed: {message}")
            self.progress_bar.setRange(0, 1)
            self.progress_bar.setValue(0)

        self.send_button.setEnabled(False)
        self.input_field.setEnabled(False)
        if hasattr(self, 'installation_complete_callback'):
            self.installation_complete_callback(success, message)

class FinishedPage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        main_frame = QFrame()
        main_frame.setFrameStyle(QFrame.NoFrame)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setOffset(0, 5)
        shadow.setColor(Qt.black)
        main_frame.setGraphicsEffect(shadow)
        layout = QVBoxLayout(main_frame)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(30)
        layout.setContentsMargins(40, 40, 40, 40)
        icon_label = QLabel()
        icon_pixmap = self.style().standardIcon(QStyle.SP_DialogApplyButton).pixmap(64, 64)
        icon_label.setPixmap(icon_pixmap)
        icon_label.setAlignment(Qt.AlignCenter)
        title = QLabel("Installation Complete!")
        title.setAlignment(Qt.AlignCenter)
        title.setObjectName("finished-title")
        message = QLabel("ObsidianOS has been successfully installed on your system.\n\nPlease remove the installation media and restart your computer.")
        message.setAlignment(Qt.AlignCenter)
        message.setWordWrap(True)
        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)
        self.restart_button = QPushButton("Restart Now")
        self.restart_button.setIcon(QIcon.fromTheme("system-reboot"))
        self.show_log_button = QPushButton("Show Log")
        button_layout.addWidget(self.restart_button)
        button_layout.addWidget(self.show_log_button)
        layout.addWidget(icon_label)
        layout.addWidget(title)
        layout.addWidget(message)
        layout.addLayout(button_layout)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(main_frame, 0, Qt.AlignCenter)
        self.setLayout(main_layout)

class ObsidianOSInstaller(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_page = 0
        self.pages = []
        self.init_ui()
        self.setup_pages()

    def init_ui(self):
        self.setWindowTitle("ObsidianOS Installer")
        self.setFixedSize(800, 600)
        app_icon = QPixmap(os.path.join(script_dir, "logo.svg"))
        if app_icon.isNull():
            app_icon = QPixmap(os.path.join("/usr/share/pixmaps", "obsidianos.png"))
        if not app_icon.isNull():
            self.setWindowIcon(QIcon(app_icon))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        self.stacked_widget = QStackedWidget()
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 20, 0, 0)
        self.back_button = QPushButton()
        self.back_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        self.back_button.clicked.connect(self.go_back)
        self.back_button.setEnabled(False)
        self.next_button = QPushButton("Next")
        self.next_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        self.next_button.clicked.connect(self.go_next)
        self.install_button = QPushButton("Install")
        self.install_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.install_button.clicked.connect(self.start_installation)
        self.install_button.hide()
        spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        button_layout.addWidget(self.back_button)
        button_layout.addItem(spacer)
        button_layout.addWidget(self.install_button)
        button_layout.addWidget(self.next_button)
        layout.addWidget(self.stacked_widget)
        layout.addLayout(button_layout)

    def setup_pages(self):
        self.pages = [
            WelcomePage(),
            DiskSelectionPage(),
            DualBootPage(),
            AdvancedOptionsPage(),
            SystemImagePage(),
            LocalePage(),
            TimezonePage(),
            KeyboardPage(),
            SummaryPage(),
            InstallationPage(),
            FinishedPage()
        ]

        for page in self.pages:
            page.setContentsMargins(30, 30, 30, 30)
            self.stacked_widget.addWidget(page)

    def go_back(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.stacked_widget.setCurrentIndex(self.current_page)
            self.update_buttons()

    def go_next(self):
        if not self.validate_current_page():
            QMessageBox.warning(self, "Validation Error", "Please make sure all required fields are filled correctly.")
            return

        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.stacked_widget.setCurrentIndex(self.current_page)
            self.update_buttons()
            if self.current_page == 8:
                self.update_summary()

    def validate_current_page(self):
        if self.current_page == 1:
            disk_page = self.pages[1]
            selected_disk = disk_page.get_selected_disk()
            if not selected_disk or selected_disk == "ERROR":
                return False
        return True

    def update_buttons(self):
        self.back_button.setEnabled(self.current_page > 0 and self.current_page < 9)
        if self.current_page == 8:
            self.next_button.hide()
            self.install_button.show()
        elif self.current_page == 9:
            self.next_button.hide()
            self.install_button.hide()
            self.back_button.setEnabled(False)
        elif self.current_page >= 10:
            self.next_button.show()
            self.next_button.setText("Finish")
            self.install_button.hide()
            self.back_button.setEnabled(False)
            try:
                self.next_button.clicked.disconnect(self.go_next)
            except TypeError:
                pass
            self.next_button.clicked.connect(self.close)
        else:
            self.next_button.show()
            self.install_button.hide()
            self.next_button.setText("Next")

    def update_summary(self):
        disk_page = self.pages[1]
        boot_page = self.pages[2]
        advanced_page = self.pages[3]
        image_page = self.pages[4]
        locale_page = self.pages[5]
        tz_page = self.pages[6]
        kb_page = self.pages[7]
        summary_page = self.pages[8]
        summary_page.update_summary(
            disk_page.get_selected_disk(),
            boot_page.get_selected_option(),
            advanced_page.get_partition_config(),
            image_page.get_selected_image(),
            locale_page.get_selected_locale(),
            tz_page.get_selected_timezone(),
            kb_page.get_selected_keyboard()
        )

    def start_installation(self):
        self.current_page = 9
        self.stacked_widget.setCurrentIndex(self.current_page)
        self.update_buttons()
        boot_page = self.pages[2]
        dual_boot_status = True if boot_page.get_selected_option().lower() == "alongside" else False
        disk_page = self.pages[1]
        advanced_page = self.pages[3]
        image_page = self.pages[4]
        locale_page = self.pages[5]
        tz_page = self.pages[6]
        kb_page = self.pages[7]
        installation_page = self.pages[9]
        installation_page.install_worker = None
        installation_page.installation_complete_callback = self.installation_finished
        installation_page.start_installation(
            disk_page.get_selected_disk(),
            image_page.get_selected_image(),
            advanced_page.get_partition_config(),
            dual_boot_status,
            advanced_page.get_filesystem_type(),
            locale_page.get_selected_locale(),
            tz_page.get_selected_timezone(),
            kb_page.get_selected_keyboard()
        )

    def installation_finished(self, success, message):
        if success:
            self.current_page = 10
            self.stacked_widget.setCurrentIndex(self.current_page)
            self.update_buttons()
            finished_page = self.pages[10]
            finished_page.restart_button.clicked.connect(self.restart_system)
            finished_page.show_log_button.clicked.connect(self.show_log)
        else:
            QMessageBox.critical(self, "Installation Failed", f"Installation failed: {message}")

    def restart_system(self):
        reply = QMessageBox.question(self, "Restart System",
                                   "Are you sure you want to restart the system now?",
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            try:
                subprocess.run(['reboot'])
            except:
                self.close()

    def show_log(self):
        log_text = self.pages[9].log_text.toPlainText()
        dialog = QDialog(self)
        dialog.setWindowTitle("Installation Log")
        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setPlainText(log_text)
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Monospace", 10))
        layout.addWidget(text_edit)
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        dialog.exec()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QWidget {
            background-color: palette(window);
            color: palette(window-text);
            font-family: sans-serif;
            font-size: 12px;
        }
        QPushButton {
            padding: 10px 18px;
            border: 1px solid palette(dark);
            border-radius: 6px;
            background-color: palette(button);
            color: palette(button-text);
        }
        QPushButton:hover {
            background-color: palette(highlight);
            color: palette(highlighted-text);
        }
        QPushButton:disabled {
            background-color: palette(mid);
            color: palette(midlight);
        }
        QLabel#welcome-title {
            font-size: 36px;
            font-weight: bold;
            color: palette(highlight);
        }
        QLabel#welcome-subtitle {
            font-size: 16px;
        }
        QLabel#page-title {
            font-size: 18px;
            font-weight: bold;
            color: palette(highlight);
        }
        QLabel#warning-label {
            font-weight: bold;
            color: palette(text);
        }
        QLabel#info-label {
            font-style: italic;
        }
        QLabel#finished-title {
            font-size: 22px;
            font-weight: bold;
            color: palette(highlight);
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid palette(dark);
            border-radius: 6px;
            margin-top: 1ex;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
        QListWidget {
            border: 1px solid palette(dark);
            border-radius: 6px;
            background-color: palette(base);
            selection-background-color: palette(highlight);
            selection-color: palette(highlighted-text);
        }
        QListWidget::item {
            padding: 8px;
        }
        QListWidget::item:hover {
            background-color: palette(alternate-base);
        }
        QListWidget#disk-list {
            alternate-background-color: palette(alternate-base);
        }
        QListWidget#image-list, QListWidget#locale-list, QListWidget#timezone-list, QListWidget#keyboard-list {
            border: 1px solid palette(dark);
            border-radius: 6px;
            background-color: palette(base);
            selection-background-color: palette(highlight);
            selection-color: palette(highlighted-text);
        }
        QListWidget#image-list::item, QListWidget#locale-list::item, QListWidget#timezone-list::item, QListWidget#keyboard-list::item {
            padding: 8px;
        }
        QListWidget#image-list::item:hover, QListWidget#locale-list::item:hover, QListWidget#timezone-list::item:hover, QListWidget#keyboard-list::item:hover {
            background-color: palette(alternate-base);
        }
        QLineEdit#search-edit {
            border: 1px solid palette(dark);
            border-radius: 6px;
            padding: 5px;
            background-color: palette(base);
        }
        QTextEdit {
            border: 1px solid palette(dark);
            border-radius: 6px;
            background-color: palette(base);
        }
        QTextEdit#log-text {
            font-family: monospace;
        }
        QWidget#input-area {
            border: 1px solid palette(dark);
            border-radius: 6px;
            background-color: palette(base);
        }
        QProgressBar {
            border: 1px solid palette(dark);
            border-radius: 6px;
            text-align: center;
            background-color: palette(base);
        }
        QProgressBar::chunk {
            background-color: palette(highlight);
            border-radius: 4px;
        }
        QFrame {
            background-color: palette(window);
            border-radius: 8px;
        }
        QGroupBox#advanced-group {
            border: 2px solid palette(highlight);
            border-radius: 8px;
        }
        QRadioButton {
            spacing: 8px;
        }
        QRadioButton::indicator {
            width: 16px;
            height: 16px;
        }
    """)
    installer = ObsidianOSInstaller()
    installer.show()
    sys.exit(app.exec())
