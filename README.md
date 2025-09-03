# ObsidianOS Installer

This repository contains the graphical installer for ObsidianOS, an A/B GNU/Linux distribution based on Arch. This installer is built using PySide6 and provides a user-friendly interface to guide you through the installation process. Comes with [ObsidianOS KDE](https://github.com/Obsidian-OS/archiso-plasma) and [ObsidianOS COSMIC](https://github.com/Obsidian-OS/archiso-cosmic).

## Features

*   **Disk Selection:** Easily select the target disk for installation.
*   **Dual Boot Configuration:** Choose to erase the entire disk or install ObsidianOS alongside an existing operating system.
*   **Advanced Partitioning:** Configure custom partition sizes for root filesystem, ESP (EFI System Partition), and A/B partitions (`etc_ab`, `var_ab`).
*   **System Image Selection:** Select the system image to be installed.
*   **Installation Progress:** Monitor the installation progress with real-time logs.
*   **System Restart:** Option to restart the system after successful installation.

## Requirements

*   Python 3
*   PySide6 library (`pacman -S pyside6`)
*   `obsidianctl` command-line tool (This tool is crucial for the actual installation process and is expected to be available in the environment where the installer is run.)
*   `lsblk` command (for disk detection)
*   `sudo` privileges for installation.

## Usage

To run the installer, execute the `installer.py` script:

```bash
python3 installer.py
```

Follow the on-screen instructions to complete the installation of ObsidianOS.

**WARNING:** The installation process will erase all data on the selected disk if you choose the "Erase entire disk" option. Please back up any important data before proceeding.

## Development

The installer is written in Python and uses the PySide6 framework for its graphical user interface.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
