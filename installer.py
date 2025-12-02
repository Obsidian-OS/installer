#!/usr/bin/env python3
import os
import pty
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

script_dir = os.path.dirname(os.path.abspath(__file__))
test_mode = "--test" in sys.argv


class InstallWorker(QThread):
    progress_updated = Signal(str)
    finished = Signal(bool, str)
    chroot_entered = Signal()

    def __init__(
        self,
        disk,
        image,
        rootfs_size,
        esp_size,
        etc_size,
        var_size,
        dual_boot,
        filesystem_type,
        locale,
        timezone,
        keyboard,
    ):
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
                    "sh",
                    "-c",
                    'echo "Test running..."; sleep 1; '
                    'echo "Partitioning disk..."; sleep 1; '
                    'echo "Installing system image..."; sleep 2; '
                    'echo "Configuring bootloader..."; sleep 1; '
                    'read -p "Do you want to proceed (y/N): " answer; echo "User answered: $answer"; '
                    "sleep 5; "
                    'echo "Installation complete"',
                ]
                self.progress_updated.emit("Starting installation...")
            else:
                cmd = [
                    "sudo",
                    "-S",
                    "obsidianctl",
                    "install",
                    self.disk,
                    self.image,
                    "--rootfs-size",
                    str(self.rootfs_size),
                    "--esp-size",
                    str(self.esp_size),
                    "--etc-size",
                    str(self.etc_size),
                    "--var-size",
                    str(self.var_size),
                ]
                if self.dual_boot:
                    cmd.append("--dual-boot")
                if self.filesystem_type == "f2fs":
                    cmd.append("--use-f2fs")
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
                bufsize=0,
            )
            os.close(slave_fd)
            import select

            while True:
                if self.process.poll() is not None:
                    try:
                        remaining_output = os.read(self.master_fd, 4096).decode(
                            errors="ignore"
                        )
                        if remaining_output:
                            for line in remaining_output.splitlines():
                                if line.strip():
                                    self.progress_updated.emit(line)
                                    if "installation complete" in line.lower():
                                        self.installation_succeeded_by_output = True
                                    elif (
                                        "error:" in line.lower()
                                        or "failed" in line.lower()
                                    ):
                                        self.installation_failed_by_output = True
                    except OSError:
                        pass
                    break

                ready, _, _ = select.select([self.master_fd], [], [], 0.1)
                if ready:
                    try:
                        output = os.read(self.master_fd, 1024).decode(errors="ignore")
                        if output:
                            for line in output.splitlines():
                                if line.strip():
                                    self.progress_updated.emit(line)
                                    if "installation complete" in line.lower():
                                        self.installation_succeeded_by_output = True
                                    elif (
                                        "error:" in line.lower()
                                        or "failed" in line.lower()
                                    ):
                                        self.installation_failed_by_output = True
                    except OSError:
                        break
            os.close(self.master_fd)
            self.master_fd = None
            if self.installation_succeeded_by_output:
                self.progress_updated.emit("Installation completed successfully!")
                self.finished.emit(True, "Installation completed successfully")
            elif self.installation_failed_by_output:
                self.finished.emit(
                    False, "Installation failed based on output messages."
                )
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
                os.write(self.master_fd, (text + "\n").encode())
            except OSError:
                pass

    def send_configs(self):
        commands = [
            f"locale-gen {self.locale} || true",
            f"localectl set-locale LANG={self.locale} || true",
            f"timedatectl set-timezone {self.timezone} || true",
            f"localectl set-keymap {self.keyboard} || true",
        ]
        for cmd in commands:
            self.send_input(cmd)


class ModernCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("modern-card")


class StepIndicator(QWidget):
    def __init__(self, steps, parent=None):
        super().__init__(parent)
        self.steps = steps
        self.current_step = 0
        self.setFixedHeight(60)

    def set_current_step(self, step):
        self.current_step = step
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        palette = self.palette()
        highlight_color = palette.highlight().color()
        text_color = palette.text().color()
        dark_color = palette.dark().color()
        base_color = palette.base().color()

        total_width = self.width() - 80
        step_width = (
            total_width / (len(self.steps) - 1) if len(self.steps) > 1 else total_width
        )

        y_center = self.height() // 2

        for i in range(len(self.steps) - 1):
            x1 = 40 + i * step_width
            x2 = 40 + (i + 1) * step_width
            if i < self.current_step:
                painter.setPen(highlight_color)
            else:
                painter.setPen(dark_color)
            painter.drawLine(int(x1), y_center, int(x2), y_center)

        for i, step in enumerate(self.steps):
            x = 40 + i * step_width
            if i < self.current_step:
                painter.setBrush(highlight_color)
                painter.setPen(highlight_color)
            elif i == self.current_step:
                painter.setBrush(highlight_color)
                painter.setPen(highlight_color)
            else:
                painter.setBrush(base_color)
                painter.setPen(dark_color)
            painter.drawEllipse(int(x - 8), y_center - 8, 16, 16)

            if i == self.current_step:
                painter.setPen(text_color)
                font = painter.font()
                font.setPointSize(8)
                painter.setFont(font)
                painter.drawText(
                    int(x - 50), y_center + 25, 100, 20, Qt.AlignCenter, step
                )


class WelcomePage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(24)
        layout.setContentsMargins(60, 40, 60, 40)

        logo_label = QLabel()
        pixmap = QPixmap(os.path.join(script_dir, "logo.svg"))
        if pixmap.isNull():
            pixmap = QPixmap(os.path.join("/usr/share/pixmaps", "obsidianos.png"))
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(
                180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            logo_label.setPixmap(scaled_pixmap)
        logo_label.setAlignment(Qt.AlignCenter)

        title = QLabel("Welcome to ObsidianOS")
        title.setObjectName("welcome-title")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("The GNU/Linux distribution with A/B Partitioning")
        subtitle.setObjectName("welcome-subtitle")
        subtitle.setAlignment(Qt.AlignCenter)

        spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        features_card = ModernCard()
        features_layout = QVBoxLayout(features_card)
        features_layout.setSpacing(16)
        features_layout.setContentsMargins(24, 24, 24, 24)

        feature_title = QLabel("What makes ObsidianOS special:")
        feature_title.setObjectName("feature-title")
        features_layout.addWidget(feature_title)

        features = [
            (
                "system-software-update",
                "Seamless A/B Updates",
                "Update without interrupting your workflow",
            ),
            (
                "security-high",
                "Instant Rollback",
                "Return to previous state if something goes wrong",
            ),
            (
                "preferences-system",
                "Mutable root",
                "Modify system files without restrictions",
            ),
        ]

        for icon_name, title_text, desc_text in features:
            feature_row = QHBoxLayout()
            feature_row.setSpacing(16)
            icon_label = QLabel()
            icon = QIcon.fromTheme(icon_name)
            if not icon.isNull():
                icon_label.setPixmap(icon.pixmap(32, 32))
            feature_row.addWidget(icon_label)

            text_layout = QVBoxLayout()
            text_layout.setSpacing(2)
            ft = QLabel(title_text)
            ft.setObjectName("feature-item-title")
            fd = QLabel(desc_text)
            fd.setObjectName("feature-item-desc")
            text_layout.addWidget(ft)
            text_layout.addWidget(fd)
            feature_row.addLayout(text_layout)
            feature_row.addStretch()

            features_layout.addLayout(feature_row)

        if test_mode:
            test_banner = QLabel("⚠ Running in Test Mode")
            test_banner.setObjectName("test-banner")
            test_banner.setAlignment(Qt.AlignCenter)
            layout.addWidget(test_banner)

        layout.addWidget(logo_label)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addItem(spacer)
        layout.addWidget(features_card)
        layout.addStretch()


class DiskSelectionPage(QWidget):
    def __init__(self):
        super().__init__()
        self.selected_disk = None
        self.init_ui()
        self.scan_disks()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 30, 40, 30)

        header = QLabel("Select Installation Disk")
        header.setObjectName("page-header")

        desc = QLabel(
            "Choose the disk where ObsidianOS will be installed. All data on the selected disk will be erased."
        )
        desc.setObjectName("page-description")
        desc.setWordWrap(True)

        card = ModernCard()
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(16)
        card_layout.setContentsMargins(20, 20, 20, 20)

        self.disk_list = QListWidget()
        self.disk_list.setObjectName("selection-list")
        self.disk_list.itemClicked.connect(self.on_disk_selected)
        self.disk_list.setMinimumHeight(200)

        card_layout.addWidget(self.disk_list)

        warning_widget = QWidget()
        warning_widget.setObjectName("warning-box")
        warning_layout = QHBoxLayout(warning_widget)
        warning_layout.setContentsMargins(16, 12, 16, 12)
        warning_layout.setSpacing(12)

        warning_icon = QLabel()
        warning_icon.setPixmap(
            self.style().standardIcon(QStyle.SP_MessageBoxWarning).pixmap(24, 24)
        )
        warning_text = QLabel(
            "Warning: All data on the selected disk will be permanently erased!"
        )
        warning_text.setObjectName("warning-text")
        warning_text.setWordWrap(True)

        warning_layout.addWidget(warning_icon)
        warning_layout.addWidget(warning_text, 1)

        layout.addWidget(header)
        layout.addWidget(desc)
        layout.addWidget(card)
        layout.addWidget(warning_widget)
        layout.addStretch()

    def scan_disks(self):
        if test_mode:
            dummy_disks = [
                ("sda", "500G", "Test SSD"),
                ("sdb", "1T", "Test HDD"),
                ("nvme0n1", "256G", "Test NVMe"),
            ]
            for name, size, model in dummy_disks:
                item = QListWidgetItem()
                item.setText(f"  /dev/{name}  •  {size}  •  {model}")
                item.setIcon(QIcon.fromTheme("drive-harddisk"))
                item.setData(Qt.UserRole, f"/dev/{name}")
                item.setSizeHint(item.sizeHint().expandedTo(item.sizeHint()))
                self.disk_list.addItem(item)
            return

        try:
            result = subprocess.run(
                ["lsblk", "-d", "-n", "-o", "NAME,SIZE,MODEL"],
                capture_output=True,
                text=True,
            )
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if line and not line.startswith("loop"):
                    parts = line.split(None, 2)
                    if len(parts) >= 2:
                        name = parts[0]
                        size = parts[1]
                        model = parts[2] if len(parts) > 2 else "Unknown"
                        item = QListWidgetItem()
                        item.setText(f"  /dev/{name}  •  {size}  •  {model}")
                        item.setIcon(QIcon.fromTheme("drive-harddisk"))
                        item.setData(Qt.UserRole, f"/dev/{name}")
                        self.disk_list.addItem(item)
        except:
            item = QListWidgetItem("  Error detecting disks")
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
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 30, 40, 30)

        header = QLabel("Installation Type")
        header.setObjectName("page-header")

        desc = QLabel("Choose how you want to install ObsidianOS on your system.")
        desc.setObjectName("page-description")
        desc.setWordWrap(True)

        self.button_group = QButtonGroup(self)

        erase_card = ModernCard()
        erase_card.setObjectName("option-card")
        erase_layout = QHBoxLayout(erase_card)
        erase_layout.setContentsMargins(20, 20, 20, 20)
        erase_layout.setSpacing(16)

        erase_icon = QLabel()
        erase_icon.setPixmap(QIcon.fromTheme("drive-harddisk").pixmap(48, 48))

        erase_text_layout = QVBoxLayout()
        erase_text_layout.setSpacing(4)
        self.erase_option = QRadioButton("Erase disk and install ObsidianOS")
        self.erase_option.setObjectName("option-radio")
        self.erase_option.setChecked(True)
        erase_desc = QLabel(
            "This will remove all existing data and operating systems from the selected disk."
        )
        erase_desc.setObjectName("option-desc")
        erase_desc.setWordWrap(True)
        erase_text_layout.addWidget(self.erase_option)
        erase_text_layout.addWidget(erase_desc)

        erase_layout.addWidget(erase_icon)
        erase_layout.addLayout(erase_text_layout, 1)
        self.button_group.addButton(self.erase_option)

        alongside_card = ModernCard()
        alongside_card.setObjectName("option-card")
        alongside_layout = QHBoxLayout(alongside_card)
        alongside_layout.setContentsMargins(20, 20, 20, 20)
        alongside_layout.setSpacing(16)

        alongside_icon = QLabel()
        alongside_icon.setPixmap(QIcon.fromTheme("drive-multidisk").pixmap(48, 48))

        alongside_text_layout = QVBoxLayout()
        alongside_text_layout.setSpacing(4)
        self.alongside_option = QRadioButton(
            "Install alongside existing OS (Dual Boot)"
        )
        self.alongside_option.setObjectName("option-radio")
        alongside_desc = QLabel(
            "Keep your existing operating system and install ObsidianOS alongside it."
        )
        alongside_desc.setObjectName("option-desc")
        alongside_desc.setWordWrap(True)
        alongside_text_layout.addWidget(self.alongside_option)
        alongside_text_layout.addWidget(alongside_desc)

        alongside_layout.addWidget(alongside_icon)
        alongside_layout.addLayout(alongside_text_layout, 1)
        self.button_group.addButton(self.alongside_option)

        layout.addWidget(header)
        layout.addWidget(desc)
        layout.addSpacing(10)
        layout.addWidget(erase_card)
        layout.addWidget(alongside_card)
        layout.addStretch()

    def get_selected_option(self):
        if self.erase_option.isChecked():
            return "erase"
        elif self.alongside_option.isChecked():
            return "alongside"
        return "erase"


class AdvancedOptionsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 30, 40, 30)

        header = QLabel("Advanced Options")
        header.setObjectName("page-header")

        desc = QLabel(
            "Configure partition sizes and filesystem options for your installation."
        )
        desc.setObjectName("page-description")
        desc.setWordWrap(True)

        card = ModernCard()
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(20)
        card_layout.setContentsMargins(24, 24, 24, 24)

        partition_label = QLabel("Partition Configuration")
        partition_label.setObjectName("section-title")
        card_layout.addWidget(partition_label)

        grid = QGridLayout()
        grid.setSpacing(16)
        grid.setColumnStretch(1, 1)

        self.rootfs_size = QSpinBox()
        self.rootfs_size.setRange(1, 9999)
        self.rootfs_size.setValue(6)
        self.rootfs_size.setSuffix(" GB")
        self.rootfs_size.setObjectName("modern-spinbox")
        grid.addWidget(QLabel("Root Filesystem (A/B):"), 0, 0)
        grid.addWidget(self.rootfs_size, 0, 1)

        self.esp_size = QSpinBox()
        self.esp_size.setRange(100, 2048)
        self.esp_size.setValue(512)
        self.esp_size.setSuffix(" MB")
        self.esp_size.setObjectName("modern-spinbox")
        grid.addWidget(QLabel("EFI System Partition:"), 1, 0)
        grid.addWidget(self.esp_size, 1, 1)

        self.etc_ab_size = QSpinBox()
        self.etc_ab_size.setRange(1, 9999)
        self.etc_ab_size.setValue(5)
        self.etc_ab_size.setSuffix(" GB")
        self.etc_ab_size.setObjectName("modern-spinbox")
        grid.addWidget(QLabel("etc_ab Partition (A/B):"), 2, 0)
        grid.addWidget(self.etc_ab_size, 2, 1)

        self.var_ab_size = QSpinBox()
        self.var_ab_size.setRange(1, 9999)
        self.var_ab_size.setValue(5)
        self.var_ab_size.setSuffix(" GB")
        self.var_ab_size.setObjectName("modern-spinbox")
        grid.addWidget(QLabel("var_ab Partition (A/B):"), 3, 0)
        grid.addWidget(self.var_ab_size, 3, 1)

        card_layout.addLayout(grid)

        fs_label = QLabel("Filesystem Type")
        fs_label.setObjectName("section-title")
        card_layout.addWidget(fs_label)

        self.filesystem_type_combo = QComboBox()
        self.filesystem_type_combo.addItem("ext4 - Standard Linux filesystem")
        self.filesystem_type_combo.addItem("f2fs - Flash-Friendly File System")
        self.filesystem_type_combo.setObjectName("modern-combo")
        card_layout.addWidget(self.filesystem_type_combo)

        info_widget = QWidget()
        info_widget.setObjectName("info-box")
        info_layout = QHBoxLayout(info_widget)
        info_layout.setContentsMargins(16, 12, 16, 12)
        info_layout.setSpacing(12)

        info_icon = QLabel()
        info_icon.setPixmap(
            self.style().standardIcon(QStyle.SP_MessageBoxInformation).pixmap(24, 24)
        )
        info_text = QLabel(
            "The A/B partition scheme creates duplicate partitions for seamless updates and instant rollback capability."
        )
        info_text.setObjectName("info-text")
        info_text.setWordWrap(True)

        info_layout.addWidget(info_icon)
        info_layout.addWidget(info_text, 1)

        layout.addWidget(header)
        layout.addWidget(desc)
        layout.addWidget(card)
        layout.addWidget(info_widget)
        layout.addStretch()

    def get_partition_config(self):
        return {
            "rootfs_size": f"{self.rootfs_size.value()}G",
            "esp_size": f"{self.esp_size.value()}M",
            "etc_ab_size": f"{self.etc_ab_size.value()}G",
            "var_ab_size": f"{self.var_ab_size.value()}G",
        }

    def get_filesystem_type(self):
        return "f2fs" if "f2fs" in self.filesystem_type_combo.currentText() else "ext4"


class SystemImagePage(QWidget):
    def __init__(self):
        super().__init__()
        self.selected_image = "/etc/system.sfs"
        self.init_ui()
        self.scan_images()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 30, 40, 30)

        header = QLabel("Select System Image")
        header.setObjectName("page-header")

        desc = QLabel(
            "Choose the system image to install. The default image is recommended for most users."
        )
        desc.setObjectName("page-description")
        desc.setWordWrap(True)

        card = ModernCard()
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(16)
        card_layout.setContentsMargins(20, 20, 20, 20)

        self.image_list = QListWidget()
        self.image_list.setObjectName("selection-list")
        self.image_list.itemClicked.connect(self.on_image_selected)
        self.image_list.setMinimumHeight(200)

        card_layout.addWidget(self.image_list)

        layout.addWidget(header)
        layout.addWidget(desc)
        layout.addWidget(card)
        layout.addStretch()

    def scan_images(self):
        default_item = QListWidgetItem()
        default_item.setText("  Default System Image")
        default_item.setIcon(QIcon.fromTheme("package-x-generic"))
        default_item.setData(Qt.UserRole, "/etc/system.sfs")
        self.image_list.addItem(default_item)
        self.image_list.setCurrentItem(default_item)

        preconf_path = Path("/usr/preconf")
        if preconf_path.exists():
            for file in preconf_path.glob("*.mkobsfs"):
                item = QListWidgetItem()
                item.setText(f"  {file.stem}")
                item.setIcon(QIcon.fromTheme("application-x-executable"))
                item.setData(Qt.UserRole, str(file))
                self.image_list.addItem(item)

        home_path = Path.home()
        for ext in ["*.mkobsfs", "*.sfs"]:
            for file in home_path.glob(ext):
                item = QListWidgetItem()
                item.setText(f"  {file.name}")
                icon_name = "folder" if ext == "*.mkobsfs" else "media-optical"
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
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 30, 40, 30)

        header = QLabel("Select Locale")
        header.setObjectName("page-header")

        desc = QLabel("Choose your preferred language and regional format settings.")
        desc.setObjectName("page-description")
        desc.setWordWrap(True)

        card = ModernCard()
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)
        card_layout.setContentsMargins(20, 20, 20, 20)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search locales...")
        self.search_edit.setObjectName("search-field")
        self.search_edit.textChanged.connect(self.filter_locales)
        self.search_edit.setClearButtonEnabled(True)

        self.locale_list = QListWidget()
        self.locale_list.setObjectName("selection-list")
        self.locale_list.itemClicked.connect(self.on_locale_selected)
        self.locale_list.setMinimumHeight(200)

        try:
            result = subprocess.run(
                ["ls", "/usr/share/locale"], capture_output=True, text=True
            )
            locales = result.stdout.strip().split("\n")
        except:
            locales = ["en_US.UTF-8"]

        for loc in locales:
            if loc.strip():
                item = QListWidgetItem()
                item.setText(f"  {loc}")
                item.setIcon(QIcon.fromTheme("preferences-desktop-locale"))
                self.locale_list.addItem(item)

        if self.locale_list.count() > 0:
            self.locale_list.setCurrentRow(0)

        card_layout.addWidget(self.search_edit)
        card_layout.addWidget(self.locale_list)

        layout.addWidget(header)
        layout.addWidget(desc)
        layout.addWidget(card)
        layout.addStretch()

    def filter_locales(self):
        text = self.search_edit.text().lower()
        for i in range(self.locale_list.count()):
            item = self.locale_list.item(i)
            item.setHidden(text not in item.text().lower())

    def on_locale_selected(self, item):
        self.selected_locale = item.text().strip()

    def get_selected_locale(self):
        return self.selected_locale


class TimezonePage(QWidget):
    def __init__(self):
        super().__init__()
        self.selected_timezone = "UTC"
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 30, 40, 30)

        header = QLabel("Select Timezone")
        header.setObjectName("page-header")

        desc = QLabel("Choose your timezone to ensure correct time display.")
        desc.setObjectName("page-description")
        desc.setWordWrap(True)

        card = ModernCard()
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)
        card_layout.setContentsMargins(20, 20, 20, 20)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search timezones...")
        self.search_edit.setObjectName("search-field")
        self.search_edit.textChanged.connect(self.filter_timezones)
        self.search_edit.setClearButtonEnabled(True)

        self.tz_list = QListWidget()
        self.tz_list.setObjectName("selection-list")
        self.tz_list.itemClicked.connect(self.on_tz_selected)
        self.tz_list.setMinimumHeight(200)

        try:
            result = subprocess.run(
                ["timedatectl", "list-timezones"], capture_output=True, text=True
            )
            timezones = result.stdout.strip().split("\n")
        except:
            timezones = ["UTC"]

        for tz in timezones:
            if tz.strip():
                item = QListWidgetItem()
                item.setText(f"  {tz}")
                item.setIcon(QIcon.fromTheme("preferences-system-time"))
                self.tz_list.addItem(item)

        if self.tz_list.count() > 0:
            self.tz_list.setCurrentRow(0)

        card_layout.addWidget(self.search_edit)
        card_layout.addWidget(self.tz_list)

        layout.addWidget(header)
        layout.addWidget(desc)
        layout.addWidget(card)
        layout.addStretch()

    def filter_timezones(self):
        text = self.search_edit.text().lower()
        for i in range(self.tz_list.count()):
            item = self.tz_list.item(i)
            item.setHidden(text not in item.text().lower())

    def on_tz_selected(self, item):
        self.selected_timezone = item.text().strip()

    def get_selected_timezone(self):
        return self.selected_timezone


class KeyboardPage(QWidget):
    def __init__(self):
        super().__init__()
        self.selected_keyboard = "us"
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 30, 40, 30)

        header = QLabel("Select Keyboard Layout")
        header.setObjectName("page-header")

        desc = QLabel("Choose the keyboard layout that matches your physical keyboard.")
        desc.setObjectName("page-description")
        desc.setWordWrap(True)

        card = ModernCard()
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)
        card_layout.setContentsMargins(20, 20, 20, 20)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search keyboard layouts...")
        self.search_edit.setObjectName("search-field")
        self.search_edit.textChanged.connect(self.filter_keyboards)
        self.search_edit.setClearButtonEnabled(True)

        self.kb_list = QListWidget()
        self.kb_list.setObjectName("selection-list")
        self.kb_list.itemClicked.connect(self.on_kb_selected)
        self.kb_list.setMinimumHeight(200)

        try:
            result = subprocess.run(
                ["localectl", "list-keymaps"], capture_output=True, text=True
            )
            keyboards = result.stdout.strip().split("\n")
        except:
            keyboards = ["us", "ar", "ru"]

        for kb in keyboards:
            if kb.strip():
                item = QListWidgetItem()
                item.setText(f"  {kb}")
                item.setIcon(QIcon.fromTheme("input-keyboard"))
                self.kb_list.addItem(item)

        if self.kb_list.count() > 0:
            self.kb_list.setCurrentRow(0)

        card_layout.addWidget(self.search_edit)
        card_layout.addWidget(self.kb_list)

        layout.addWidget(header)
        layout.addWidget(desc)
        layout.addWidget(card)
        layout.addStretch()

    def filter_keyboards(self):
        text = self.search_edit.text().lower()
        for i in range(self.kb_list.count()):
            item = self.kb_list.item(i)
            item.setHidden(text not in item.text().lower())

    def on_kb_selected(self, item):
        self.selected_keyboard = item.text().strip()

    def get_selected_keyboard(self):
        return self.selected_keyboard


class SummaryPage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 30, 40, 30)

        header = QLabel("Review Installation Settings")
        header.setObjectName("page-header")

        desc = QLabel("Please review your settings before starting the installation.")
        desc.setObjectName("page-description")
        desc.setWordWrap(True)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("summary-scroll")

        card = ModernCard()
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(16)
        card_layout.setContentsMargins(24, 24, 24, 24)

        self.summary_grid = QGridLayout()
        self.summary_grid.setSpacing(12)
        self.summary_grid.setColumnStretch(1, 1)

        self.summary_items = {}
        items = [
            ("disk", "drive-harddisk", "Installation Target"),
            ("boot", "system-run", "Installation Type"),
            ("image", "package-x-generic", "System Image"),
            ("locale", "preferences-desktop-locale", "Locale"),
            ("timezone", "preferences-system-time", "Timezone"),
            ("keyboard", "input-keyboard", "Keyboard Layout"),
            ("partitions", "drive-multidisk", "Partition Layout"),
        ]

        for i, (key, icon_name, label_text) in enumerate(items):
            icon_label = QLabel()
            icon = QIcon.fromTheme(icon_name)
            if not icon.isNull():
                icon_label.setPixmap(icon.pixmap(20, 20))

            name_label = QLabel(label_text + ":")
            name_label.setObjectName("summary-label")

            value_label = QLabel()
            value_label.setObjectName("summary-value")
            value_label.setWordWrap(True)
            self.summary_items[key] = value_label

            self.summary_grid.addWidget(icon_label, i, 0)
            self.summary_grid.addWidget(name_label, i, 1)
            self.summary_grid.addWidget(value_label, i, 2)

        card_layout.addLayout(self.summary_grid)
        scroll.setWidget(card)

        warning_widget = QWidget()
        warning_widget.setObjectName("warning-box")
        warning_layout = QHBoxLayout(warning_widget)
        warning_layout.setContentsMargins(16, 12, 16, 12)
        warning_layout.setSpacing(12)

        warning_icon = QLabel()
        warning_icon.setPixmap(
            self.style().standardIcon(QStyle.SP_MessageBoxWarning).pixmap(24, 24)
        )
        warning_text = QLabel(
            "Click 'Install' to begin. This process cannot be undone!"
        )
        warning_text.setObjectName("warning-text")
        warning_text.setWordWrap(True)

        warning_layout.addWidget(warning_icon)
        warning_layout.addWidget(warning_text, 1)

        layout.addWidget(header)
        layout.addWidget(desc)
        layout.addWidget(scroll, 1)
        layout.addWidget(warning_widget)

    def update_summary(
        self, disk, boot_option, partition_config, image, locale, timezone, keyboard
    ):
        self.summary_items["disk"].setText(disk or "Not selected")
        self.summary_items["boot"].setText(
            "Erase disk" if boot_option == "erase" else "Dual boot"
        )
        self.summary_items["image"].setText(image or "Default")
        self.summary_items["locale"].setText(locale)
        self.summary_items["timezone"].setText(timezone)
        self.summary_items["keyboard"].setText(keyboard)

        partitions_text = (
            f"ESP: {partition_config['esp_size']} | "
            f"Root: {partition_config['rootfs_size']} (A/B) | "
            f"etc: {partition_config['etc_ab_size']} (A/B) | "
            f"var: {partition_config['var_ab_size']} (A/B)"
        )
        self.summary_items["partitions"].setText(partitions_text)


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
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(40, 30, 40, 30)

        header = QLabel("Installing ObsidianOS")
        header.setObjectName("page-header")

        self.status_label = QLabel("Preparing installation...")
        self.status_label.setObjectName("status-label")
        self.status_label.setAlignment(Qt.AlignCenter)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setObjectName("modern-progress")
        self.progress_bar.setMinimumHeight(8)
        self.progress_bar.setTextVisible(False)

        card = ModernCard()
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)
        card_layout.setContentsMargins(16, 16, 16, 16)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Monospace", 9))
        self.log_text.setObjectName("log-output")
        self.log_text.setMinimumHeight(200)

        card_layout.addWidget(self.log_text)

        input_card = ModernCard()
        input_card.setObjectName("input-card")
        input_layout = QVBoxLayout(input_card)
        input_layout.setSpacing(8)
        input_layout.setContentsMargins(16, 12, 16, 12)

        self.question_label = QLabel()
        self.question_label.setObjectName("question-label")
        self.question_label.hide()

        button_row = QHBoxLayout()
        button_row.setSpacing(12)
        self.yes_button = QPushButton("Yes")
        self.yes_button.setObjectName("action-button")
        self.no_button = QPushButton("No")
        self.no_button.setObjectName("action-button")
        self.yes_button.hide()
        self.no_button.hide()
        button_row.addWidget(self.yes_button)
        button_row.addWidget(self.no_button)
        button_row.addStretch()

        text_row = QHBoxLayout()
        text_row.setSpacing(8)
        self.input_field = QLineEdit()
        self.input_field.setObjectName("command-input")
        self.input_field.setPlaceholderText("Enter command...")
        self.send_button = QPushButton()
        self.send_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        self.send_button.setObjectName("send-button")
        self.send_button.clicked.connect(self.send_input)
        text_row.addWidget(self.input_field, 1)
        text_row.addWidget(self.send_button)

        input_layout.addWidget(self.question_label)
        input_layout.addLayout(button_row)
        input_layout.addLayout(text_row)

        layout.addWidget(header)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(card, 1)
        layout.addWidget(input_card)

        self.yes_button.clicked.connect(lambda: self.send_y_n("y"))
        self.no_button.clicked.connect(lambda: self.send_y_n("n"))
        self.input_field.returnPressed.connect(self.send_input)
        self.is_y_n_prompt_active = False

    def send_input(self):
        if self.is_y_n_prompt_active:
            return
        if self.install_worker:
            text = self.input_field.text().strip()
            if text:
                self.install_worker.send_input(text)
                self.log_text.append(f">>> {text}")
                self.input_field.clear()

    def send_y_n(self, choice):
        if self.install_worker:
            self.install_worker.send_input(choice)
            self.log_text.append(f">>> {choice}")
            self.question_label.hide()
            self.yes_button.hide()
            self.no_button.hide()
            self.input_field.show()
            self.send_button.show()
            self.is_y_n_prompt_active = False
            self.input_field.clear()

    def start_installation(
        self,
        disk,
        image,
        partition_config,
        dual_boot,
        filesystem_type,
        locale,
        timezone,
        keyboard,
    ):
        self.status_label.setText("Starting installation...")
        self.log_text.clear()
        self.selected_locale = locale
        self.selected_timezone = timezone
        self.selected_keyboard = keyboard
        self.install_worker = InstallWorker(
            disk,
            image,
            partition_config["rootfs_size"],
            partition_config["esp_size"],
            partition_config["etc_ab_size"],
            partition_config["var_ab_size"],
            dual_boot,
            filesystem_type,
            locale,
            timezone,
            keyboard,
        )
        self.install_worker.progress_updated.connect(self.update_progress)
        self.install_worker.finished.connect(self.installation_finished)
        self.install_worker.chroot_entered.connect(self.on_chroot_entered)
        self.install_worker.start()

    def on_chroot_entered(self):
        reply = QMessageBox.question(
            self,
            "Chroot",
            "You are now in chroot. Do you still want to be in chroot?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply == QMessageBox.No:
            self.install_worker.send_input("exit")

    def update_progress(self, message):
        self.status_label.setText("Installation in progress...")
        if (
            "Do you want to chroot into slot 'a' to make changes before copying it to slot B? (y/N):"
            in message
        ):
            self.install_worker.send_input("y")
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
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
        else:
            self.status_label.setText(f"Installation failed: {message}")
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
        self.send_button.setEnabled(False)
        self.input_field.setEnabled(False)
        if hasattr(self, "installation_complete_callback"):
            self.installation_complete_callback(success, message)


class FinishedPage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(24)
        layout.setContentsMargins(60, 40, 60, 40)

        icon_label = QLabel()
        icon_label.setPixmap(QIcon.fromTheme("emblem-ok-symbolic").pixmap(96, 96))
        icon_label.setAlignment(Qt.AlignCenter)

        title = QLabel("Installation Complete!")
        title.setObjectName("finished-title")
        title.setAlignment(Qt.AlignCenter)

        message = QLabel(
            "ObsidianOS has been successfully installed on your system.\n\n"
            "Please remove the installation media and restart your computer."
        )
        message.setObjectName("finished-message")
        message.setAlignment(Qt.AlignCenter)
        message.setWordWrap(True)

        card = ModernCard()
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(16)
        card_layout.setContentsMargins(32, 32, 32, 32)
        card_layout.setAlignment(Qt.AlignCenter)

        card_layout.addWidget(icon_label)
        card_layout.addWidget(title)
        card_layout.addWidget(message)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(16)

        self.show_log_button = QPushButton("View Log")
        self.show_log_button.setObjectName("secondary-button")
        self.show_log_button.setIcon(QIcon.fromTheme("document-open"))

        self.restart_button = QPushButton("Restart Now")
        self.restart_button.setObjectName("primary-button")
        self.restart_button.setIcon(QIcon.fromTheme("system-reboot"))

        button_layout.addStretch()
        button_layout.addWidget(self.show_log_button)
        button_layout.addWidget(self.restart_button)
        button_layout.addStretch()

        card_layout.addSpacing(16)
        card_layout.addLayout(button_layout)

        layout.addStretch()
        layout.addWidget(card)
        layout.addStretch()


class ObsidianOSInstaller(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_page = 0
        self.pages = []
        self.init_ui()
        self.setup_pages()

    def init_ui(self):
        self.setWindowTitle("ObsidianOS Installer")
        self.setMinimumSize(900, 900)
        self.resize(900, 900)
        app_icon = QPixmap(os.path.join(script_dir, "logo.svg"))
        if app_icon.isNull():
            app_icon = QPixmap(os.path.join("/usr/share/pixmaps", "obsidianos.png"))
        if not app_icon.isNull():
            self.setWindowIcon(QIcon(app_icon))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.step_indicator = StepIndicator(
            [
                "Welcome",
                "Disk",
                "Type",
                "Options",
                "Image",
                "Locale",
                "Time",
                "Keyboard",
                "Summary",
                "Install",
                "Done",
            ]
        )
        self.step_indicator.setObjectName("step-indicator")

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self.stacked_widget = QStackedWidget()

        button_bar = QWidget()
        button_bar.setObjectName("button-bar")
        button_layout = QHBoxLayout(button_bar)
        button_layout.setContentsMargins(24, 16, 24, 16)
        button_layout.setSpacing(12)

        self.back_button = QPushButton("Back")
        self.back_button.setObjectName("nav-button")
        self.back_button.setIcon(QIcon.fromTheme("go-previous"))
        self.back_button.clicked.connect(self.go_back)
        self.back_button.setEnabled(False)

        self.next_button = QPushButton("Continue")
        self.next_button.setObjectName("nav-button-primary")
        self.next_button.setIcon(QIcon.fromTheme("go-next"))
        self.next_button.setLayoutDirection(Qt.RightToLeft)
        self.next_button.clicked.connect(self.go_next)

        self.install_button = QPushButton("Install")
        self.install_button.setObjectName("install-button")
        self.install_button.setIcon(QIcon.fromTheme("system-software-install"))
        self.install_button.clicked.connect(self.start_installation)
        self.install_button.hide()

        button_layout.addWidget(self.back_button)
        button_layout.addStretch()
        button_layout.addWidget(self.install_button)
        button_layout.addWidget(self.next_button)

        content_layout.addWidget(self.stacked_widget, 1)
        content_layout.addWidget(button_bar)

        main_layout.addWidget(self.step_indicator)
        main_layout.addWidget(content_widget, 1)

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
            FinishedPage(),
        ]
        for page in self.pages:
            self.stacked_widget.addWidget(page)

    def go_back(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.stacked_widget.setCurrentIndex(self.current_page)
            self.step_indicator.set_current_step(self.current_page)
            self.update_buttons()

    def go_next(self):
        if not self.validate_current_page():
            QMessageBox.warning(
                self,
                "Validation Error",
                "Please make sure all required fields are filled correctly.",
            )
            return
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.stacked_widget.setCurrentIndex(self.current_page)
            self.step_indicator.set_current_step(self.current_page)
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
            self.next_button.setIcon(QIcon.fromTheme("application-exit"))
            self.install_button.hide()
            self.back_button.setEnabled(False)
            try:
                self.next_button.clicked.disconnect(self.go_next)
            except TypeError:
                pass
            self.next_button.clicked.connect(self.close)
        else:
            self.next_button.show()
            self.next_button.setText("Continue")
            self.next_button.setIcon(QIcon.fromTheme("go-next"))
            self.install_button.hide()

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
            kb_page.get_selected_keyboard(),
        )

    def start_installation(self):
        self.current_page = 9
        self.stacked_widget.setCurrentIndex(self.current_page)
        self.step_indicator.set_current_step(self.current_page)
        self.update_buttons()
        boot_page = self.pages[2]
        dual_boot_status = boot_page.get_selected_option().lower() == "alongside"
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
            kb_page.get_selected_keyboard(),
        )

    def installation_finished(self, success, message):
        if success:
            self.current_page = 10
            self.stacked_widget.setCurrentIndex(self.current_page)
            self.step_indicator.set_current_step(self.current_page)
            self.update_buttons()
            finished_page = self.pages[10]
            finished_page.restart_button.clicked.connect(self.restart_system)
            finished_page.show_log_button.clicked.connect(self.show_log)
        else:
            QMessageBox.critical(
                self, "Installation Failed", f"Installation failed: {message}"
            )

    def restart_system(self):
        reply = QMessageBox.question(
            self,
            "Restart System",
            "Are you sure you want to restart the system now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply == QMessageBox.Yes:
            try:
                subprocess.run(["reboot"])
            except:
                self.close()

    def show_log(self):
        log_text = self.pages[9].log_text.toPlainText()
        dialog = QDialog(self)
        dialog.setWindowTitle("Installation Log")
        dialog.resize(700, 500)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        text_edit = QTextEdit()
        text_edit.setPlainText(log_text)
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Monospace", 9))
        layout.addWidget(text_edit)
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        dialog.exec()


STYLESHEET = """
QWidget {
    background-color: transparent;
    font-family: "Noto Sans", sans-serif;
    font-size: 10pt;
}

QLabel#welcome-title {
    font-size: 28pt;
    font-weight: bold;
    color: palette(highlight);
}

QLabel#welcome-subtitle {
    font-size: 12pt;
}

QLabel#page-header {
    font-size: 18pt;
    font-weight: bold;
    padding-bottom: 4px;
}

QLabel#page-description {
    font-size: 10pt;
    padding-bottom: 8px;
}

QLabel#section-title {
    font-size: 11pt;
    font-weight: bold;
    color: palette(highlight);
    padding-top: 8px;
}

QLabel#feature-title {
    font-size: 11pt;
    font-weight: bold;
}

QLabel#feature-item-title {
    font-size: 10pt;
    font-weight: bold;
}

QLabel#feature-item-desc {
    font-size: 9pt;
}

QLabel#test-banner {
    background-color: palette(highlight);
    color: palette(highlighted-text);
    font-weight: bold;
    padding: 8px 16px;
    border-radius: 4px;
}

QLabel#finished-title {
    font-size: 22pt;
    font-weight: bold;
    color: palette(highlight);
}

QLabel#finished-message {
    font-size: 11pt;
}

QLabel#status-label {
    font-size: 11pt;
    color: palette(highlight);
}

QLabel#summary-label {
    font-weight: bold;
}

QLabel#warning-text {
    font-weight: bold;
}

QLabel#option-desc {
    font-size: 9pt;
}

QFrame#modern-card {
    background-color: palette(base);
    border: 1px solid palette(mid);
    border-radius: 8px;
}

QFrame#option-card {
    background-color: palette(base);
    border: 1px solid palette(mid);
    border-radius: 8px;
}

QFrame#option-card:hover {
    border-color: palette(highlight);
}

QWidget#warning-box {
    border: 1px solid palette(mid);
    border-radius: 6px;
}

QWidget#info-box {
    border: 1px solid palette(highlight);
    border-radius: 6px;
}

QWidget#button-bar {
    background-color: palette(window);
    border-top: 1px solid palette(mid);
}

QWidget#step-indicator {
    background-color: palette(window);
    border-bottom: 1px solid palette(mid);
}

QPushButton {
    background-color: palette(button);
    border: 1px solid palette(mid);
    border-radius: 6px;
    padding: 10px 20px;
    color: palette(button-text);
    font-weight: bold;
}

QPushButton:hover {
    background-color: palette(light);
    border-color: palette(highlight);
}

QPushButton:pressed {
    background-color: palette(dark);
}

QPushButton:disabled {
    background-color: palette(window);
    color: palette(mid);
    border-color: palette(mid);
}

QPushButton#nav-button-primary, QPushButton#install-button {
    background-color: palette(highlight);
    border: none;
    color: palette(highlighted-text);
}

QPushButton#nav-button-primary:hover, QPushButton#install-button:hover {
    background-color: palette(light);
}

QPushButton#nav-button-primary:pressed, QPushButton#install-button:pressed {
    background-color: palette(dark);
}

QPushButton#primary-button {
    background-color: palette(highlight);
    border: none;
    color: palette(highlighted-text);
    padding: 12px 24px;
}

QPushButton#primary-button:hover {
    background-color: palette(light);
}

QPushButton#secondary-button {
    background-color: transparent;
    border: 1px solid palette(mid);
    padding: 12px 24px;
}

QPushButton#secondary-button:hover {
    border-color: palette(highlight);
}

QPushButton#send-button {
    padding: 8px 12px;
    min-width: 40px;
}

QPushButton#action-button {
    padding: 8px 16px;
    min-width: 80px;
}

QListWidget#selection-list {
    background-color: palette(base);
    border: 1px solid palette(mid);
    border-radius: 6px;
    outline: none;
}

QListWidget#selection-list::item {
    padding: 12px 8px;
    border-bottom: 1px solid palette(mid);
}

QListWidget#selection-list::item:last {
    border-bottom: none;
}

QListWidget#selection-list::item:hover {
    background-color: palette(alternate-base);
}

QListWidget#selection-list::item:selected {
    background-color: palette(highlight);
    color: palette(highlighted-text);
}

QLineEdit, QLineEdit#search-field, QLineEdit#command-input {
    background-color: palette(base);
    border: 1px solid palette(mid);
    border-radius: 6px;
    padding: 10px 12px;
    color: palette(text);
    selection-background-color: palette(highlight);
}

QLineEdit:focus {
    border-color: palette(highlight);
}

QTextEdit, QTextEdit#log-output {
    background-color: palette(base);
    border: 1px solid palette(mid);
    border-radius: 6px;
    padding: 8px;
    color: palette(text);
    selection-background-color: palette(highlight);
}

QSpinBox, QSpinBox#modern-spinbox {
    background-color: palette(base);
    border: 1px solid palette(mid);
    border-radius: 6px;
    padding: 8px 12px;
    color: palette(text);
    min-width: 120px;
}

QSpinBox:focus {
    border-color: palette(highlight);
}

QSpinBox::up-button, QSpinBox::down-button {
    background-color: palette(button);
    border: none;
    width: 20px;
    subcontrol-origin: border;
}

QSpinBox::up-button {
    subcontrol-position: top right;
    border-top-right-radius: 4px;
}

QSpinBox::down-button {
    subcontrol-position: bottom right;
    border-bottom-right-radius: 4px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: palette(light);
}

QSpinBox::up-arrow {
    image: url({{UPARROW_PATH}});
    width: 10px;
    height: 10px;
}

QSpinBox::down-arrow {
    image: url({{DOWNARROW_PATH}});
    width: 10px;
    height: 10px;
}

QComboBox, QComboBox#modern-combo {
    background-color: palette(base);
    border: 1px solid palette(mid);
    border-radius: 6px;
    padding: 10px 12px;
    color: palette(text);
    min-width: 200px;
}

QComboBox:focus {
    border-color: palette(highlight);
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 30px;
    border: none;
}

QComboBox::down-arrow {
    image: url({{DROPDOWN_PATH}});
    width: 12px;
    height: 12px;
}

QComboBox QAbstractItemView {
    background-color: palette(base);
    border: 1px solid palette(mid);
    selection-background-color: palette(highlight);
    selection-color: palette(highlighted-text);
}

QRadioButton {
    spacing: 10px;
}

QRadioButton#option-radio {
    font-weight: bold;
    font-size: 11pt;
}

QRadioButton::indicator {
    width: 20px;
    height: 20px;
    border-radius: 4px;
    border: 2px solid palette(mid);
    background-color: palette(base);
}

QRadioButton::indicator:hover {
    border-color: palette(highlight);
}

QRadioButton::indicator:checked {
    border-color: palette(highlight);
    background-color: palette(highlight);
    image: url({{CHECKMARK_PATH}});
}

QProgressBar, QProgressBar#modern-progress {
    background-color: palette(base);
    border: none;
    border-radius: 4px;
    height: 8px;
}

QProgressBar::chunk {
    background-color: palette(highlight);
    border-radius: 4px;
}

QScrollArea, QScrollArea#summary-scroll {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    background-color: palette(base);
    width: 12px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background-color: palette(mid);
    border-radius: 6px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: palette(dark);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: palette(base);
    height: 12px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal {
    background-color: palette(mid);
    border-radius: 6px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background-color: palette(dark);
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

QFrame#input-card {
    background-color: palette(base);
    border: 1px solid palette(mid);
    border-radius: 6px;
}

QLabel#question-label {
    font-weight: bold;
    padding: 4px 0;
}
"""
CHECKMARK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>"""

DROPDOWN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="gray" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>"""

UPARROW_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="gray" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 15 12 9 6 15"></polyline></svg>"""

DOWNARROW_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="gray" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>"""


def create_temp_svg(content):
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False)
    f.write(content)
    f.close()
    return f.name.replace("\\", "/")


if __name__ == "__main__":
    checkmark_path = create_temp_svg(CHECKMARK_SVG)
    dropdown_path = create_temp_svg(DROPDOWN_SVG)
    uparrow_path = create_temp_svg(UPARROW_SVG)
    downarrow_path = create_temp_svg(DOWNARROW_SVG)

    app = QApplication(sys.argv)
    stylesheet = STYLESHEET.replace("{{CHECKMARK_PATH}}", checkmark_path)
    stylesheet = stylesheet.replace("{{DROPDOWN_PATH}}", dropdown_path)
    stylesheet = stylesheet.replace("{{UPARROW_PATH}}", uparrow_path)
    stylesheet = stylesheet.replace("{{DOWNARROW_PATH}}", downarrow_path)
    app.setStyleSheet(stylesheet)
    installer = ObsidianOSInstaller()
    installer.show()
    result = app.exec()
    os.unlink(checkmark_path)
    os.unlink(dropdown_path)
    os.unlink(uparrow_path)
    os.unlink(downarrow_path)
    sys.exit(result)
