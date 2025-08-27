#!/usr/bin/env python3
import sys
import os
import subprocess
import time
from pathlib import Path
script_dir = os.path.dirname(os.path.abspath(__file__))
from PySide6.QtWidgets import (QApplication, QMainWindow, QStackedWidget, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel, QListWidget, QRadioButton, QButtonGroup, QProgressBar, QTextEdit, QFrame, QSpacerItem, QSizePolicy, QListWidgetItem, QSpinBox, QFormLayout, QGroupBox, QMessageBox, QComboBox)
from PySide6.QtCore import Qt, QThread, QTimer, Signal, QProcess
from PySide6.QtGui import QFont, QPalette, QPixmap, QIcon, QTextCursor
import pty

class InstallWorker(QThread):
    progress_updated = Signal(str)
    finished = Signal(bool, str)
    def __init__(self, disk, image, rootfs_size, esp_size, etc_size, var_size, dual_boot, filesystem_type):
        super().__init__()
        self.disk = disk
        self.image = image
        self.rootfs_size = rootfs_size
        self.esp_size = esp_size
        self.etc_size = etc_size
        self.var_size = var_size
        self.dual_boot = dual_boot
        self.filesystem_type = filesystem_type
        self.process = None
        self.master_fd = None
        self.installation_succeeded_by_output = False
        self.installation_failed_by_output = False

    def run(self):
        try:
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
            master_fd, slave_fd = pty.openpty()
            self.master_fd = master_fd
            self.process = subprocess.Popen(
                cmd,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                preexec_fn=os.setsid,
                text=False,
                bufsize=0
            )
            os.close(slave_fd)
            import select
            while True:
                if self.process.poll() is not None:
                    try:
                        remaining_output = os.read(self.master_fd, 4096).decode(errors='ignore')
                        if remaining_output:
                            for line in remaining_output.splitlines():
                                if line.strip():
                                    self.progress_updated.emit(line)
                                    if "Installation complete!" in line:
                                        self.installation_succeeded_by_output = True
                                    elif "Error:" in line or "failed" in line.lower():
                                        self.installation_failed_by_output = True
                    except OSError:
                        pass
                    break

                ready, _, _ = select.select([self.master_fd], [], [], 0.1)
                if ready:
                    try:
                        output = os.read(self.master_fd, 1024).decode(errors='ignore')
                        if output:
                            for line in output.splitlines():
                                if line.strip():
                                    self.progress_updated.emit(line)
                                    if "Installation complete!" in line:
                                        self.installation_succeeded_by_output = True
                                    elif "Error:" in line or "failed" in line.lower():
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
        font = QFont()
        font.setPointSize(24)
        font.setBold(True)
        title.setFont(font)
        subtitle = QLabel("An A/B GNU/Linux distro based on Arch.")
        subtitle.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(14)
        subtitle.setFont(font)
        description = QLabel("Let's start the installation now!")
        description.setAlignment(Qt.AlignCenter)
        description.setWordWrap(True)
        logo_label = QLabel()
        pixmap = QPixmap(os.path.join(script_dir, "logo.png"))
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
        layout = QVBoxLayout()
        title = QLabel("Select Installation Disk")
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        self.disk_list = QListWidget()
        self.disk_list.itemClicked.connect(self.on_disk_selected)
        warning = QLabel("⚠️ All data on the selected disk will be erased!")
        warning_font = QFont()
        warning_font.setBold(True)
        warning.setFont(warning_font)
        palette = warning.palette()
        palette.setColor(QPalette.WindowText, Qt.red)
        warning.setPalette(palette)
        layout.addWidget(title)
        layout.addWidget(self.disk_list)
        layout.addWidget(warning)
        self.setLayout(layout)

    def scan_disks(self):
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
                        item.setData(Qt.UserRole, f"/dev/{name}")
                        self.disk_list.addItem(item)
        except:
            item = QListWidgetItem("ERROR DETECTING DISKS")
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
        layout = QVBoxLayout()
        title = QLabel("Dual Boot Configuration")
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        self.button_group = QButtonGroup()
        self.erase_option = QRadioButton("Erase entire disk and install ObsidianOS")
        self.erase_option.setChecked(True)
        self.alongside_option = QRadioButton("Install ObsidianOS alongside existing OS")
        self.button_group.addButton(self.erase_option)
        self.button_group.addButton(self.alongside_option)
        description = QLabel("Choose how you want to install ObsidianOS:")
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(self.erase_option)
        layout.addWidget(self.alongside_option)
        layout.addStretch()
        self.setLayout(layout)

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
        layout = QVBoxLayout()
        title = QLabel("Advanced Options")
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        description = QLabel("Configure partition sizes for your ObsidianOS installation:")
        description.setWordWrap(True)
        group_box = QGroupBox("Partition Configuration")
        form_layout = QFormLayout()
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
        info_label = QLabel("ℹ️ The A/B system requires duplicate partitions for safe updates and rollback capabilities.")
        info_label.setWordWrap(True)
        info_font = QFont()
        info_font.setItalic(True)
        info_label.setFont(info_font)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(group_box)
        layout.addWidget(info_label)
        layout.addStretch()
        self.setLayout(layout)

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
        layout = QVBoxLayout()
        title = QLabel("Select System Image")
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        self.image_list = QListWidget()
        self.image_list.itemClicked.connect(self.on_image_selected)
        layout.addWidget(title)
        layout.addWidget(self.image_list)
        self.setLayout(layout)

    def scan_images(self):
        default_item = QListWidgetItem("📦 Default System Image")
        default_item.setData(Qt.UserRole, "/etc/system.sfs")
        self.image_list.addItem(default_item)
        self.image_list.setCurrentItem(default_item)
        preconf_path = Path("/usr/preconf")
        if preconf_path.exists():
            for file in preconf_path.glob("*.mkobsfs"):
                item = QListWidgetItem(f"🔧 {file.stem}")
                item.setData(Qt.UserRole, str(file))
                self.image_list.addItem(item)

        home_path = Path.home()
        for ext in ["*.mkobsfs", "*.sfs"]:
            for file in home_path.glob(ext):
                icon = "📁" if ext == "*.mkobsfs" else "💿"
                item = QListWidgetItem(f"{icon} {file.name}")
                item.setData(Qt.UserRole, str(file))
                self.image_list.addItem(item)

    def on_image_selected(self, item):
        self.selected_image = item.data(Qt.UserRole)

    def get_selected_image(self):
        return self.selected_image

class SummaryPage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        title = QLabel("Installation Summary")
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        self.summary_text = QLabel()
        self.summary_text.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        self.summary_text.setWordWrap(True)
        self.summary_text.setMargin(15)
        warning = QLabel("⚠️ Click 'Install' to begin the installation process. This cannot be undone!")
        warning_font = QFont()
        warning_font.setBold(True)
        warning.setFont(warning_font)
        palette = warning.palette()
        palette.setColor(QPalette.WindowText, Qt.red)
        warning.setPalette(palette)
        layout.addWidget(title)
        layout.addWidget(self.summary_text)
        layout.addWidget(warning)
        layout.addStretch()
        self.setLayout(layout)

    def update_summary(self, disk, boot_option, partition_config, image):
        summary = f"""<b>Installation Target:</b> {disk or 'Not selected'}<br><br>
<b>Boot Configuration:</b> {boot_option.replace('_', ' ').title()}<br><br>
<b>System Image:</b> {image or 'Default'}<br><br>
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
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        title = QLabel("Installing ObsidianOS")
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        self.status_label = QLabel("Preparing installation...")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier", 10))
        input_layout = QHBoxLayout()
        self.input_field = QTextEdit()
        self.input_field.setMaximumHeight(30)
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_input)
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_button)
        layout.addWidget(title)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.log_text)
        layout.addLayout(input_layout)
        self.setLayout(layout)

    def send_input(self):
        if self.install_worker:
            text = self.input_field.toPlainText().strip()
            if text:
                self.install_worker.send_input(text)
                self.log_text.append(f">>> {text}")
                self.input_field.clear()

    def start_installation(self, disk, image, partition_config, dual_boot, filesystem_type):
        self.status_label.setText("Starting installation...")
        self.log_text.clear()
        self.install_worker = InstallWorker(
            disk, image,
            partition_config['rootfs_size'],
            partition_config['esp_size'],
            partition_config['etc_ab_size'],
            partition_config['var_ab_size'],
            dual_boot,
            filesystem_type
        )

        self.install_worker.progress_updated.connect(self.update_progress)
        self.install_worker.finished.connect(self.installation_finished)
        self.install_worker.start()

    def update_progress(self, message):
        self.status_label.setText("Installation in progress...")
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
        if hasattr(self.parent(), 'installation_complete_callback'):
            self.parent().installation_complete_callback(success, message)

class FinishedPage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(30)
        title = QLabel("Installation Complete!")
        title.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        title.setFont(font)
        palette = title.palette()
        palette.setColor(QPalette.WindowText, Qt.darkGreen)
        title.setPalette(palette)
        message = QLabel("ObsidianOS has been successfully installed on your system.\nPlease remove the installation media and restart your computer.")
        message.setAlignment(Qt.AlignCenter)
        message.setWordWrap(True)
        self.restart_button = QPushButton("Restart Now")
        layout.addWidget(title)
        layout.addWidget(message)
        layout.addWidget(self.restart_button)
        self.setLayout(layout)

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
        app_icon = QPixmap(os.path.join(script_dir, "logo.png"))
        if not app_icon.isNull():
            self.setWindowIcon(QIcon(app_icon))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        self.stacked_widget = QStackedWidget()
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 20, 0, 0)
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self.go_back)
        self.back_button.setEnabled(False)
        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.go_next)
        self.install_button = QPushButton("Install")
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
            if self.current_page == 5:
                self.update_summary()

    def validate_current_page(self):
        if self.current_page == 1:
            disk_page = self.pages[1]
            selected_disk = disk_page.get_selected_disk()
            if not selected_disk or selected_disk == "ERROR":
                return False
        return True

    def update_buttons(self):
        self.back_button.setEnabled(self.current_page > 0 and self.current_page < 6)
        if self.current_page == 5:
            self.next_button.hide()
            self.install_button.show()
        elif self.current_page == 6:
            self.next_button.hide()
            self.install_button.hide()
            self.back_button.setEnabled(False)
        elif self.current_page >= 7:
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
        summary_page = self.pages[5]
        summary_page.update_summary(
            disk_page.get_selected_disk(),
            boot_page.get_selected_option(),
            advanced_page.get_partition_config(),
            image_page.get_selected_image()
        )

    def start_installation(self):
        self.current_page = 6
        self.stacked_widget.setCurrentIndex(self.current_page)
        self.update_buttons()
        boot_page = self.pages[2]
        dual_boot_status = True if boot_page.get_selected_option().lower() == "alongside" else False
        disk_page = self.pages[1]
        advanced_page = self.pages[3]
        image_page = self.pages[4]
        installation_page = self.pages[6]
        installation_page.install_worker = None
        installation_page.installation_complete_callback = self.installation_finished
        installation_page.start_installation(
            disk_page.get_selected_disk(),
            image_page.get_selected_image(),
            advanced_page.get_partition_config(),
            dual_boot_status,
            advanced_page.get_filesystem_type()
        )

    def installation_finished(self, success, message):
        if success:
            self.current_page = 7
            self.stacked_widget.setCurrentIndex(self.current_page)
            self.update_buttons()
            finished_page = self.pages[7]
            finished_page.restart_button.clicked.connect(self.restart_system)
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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    installer = ObsidianOSInstaller()
    installer.show()
    sys.exit(app.exec())
