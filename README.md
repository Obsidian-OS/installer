# ObsidianOS Installer

This repository contains the graphical installer for ObsidianOS, an A/B GNU/Linux distribution based on Arch. This installer is built using PySide6 and provides a user-friendly interface to guide you through the installation process. Comes with [ObsidianOS KDE](https://github.com/Obsidian-OS/archiso-plasma) and [ObsidianOS COSMIC](https://github.com/Obsidian-OS/archiso-cosmic).

## Screenshots
<img width="887" height="685" alt="Intro Page" src="https://github.com/user-attachments/assets/78db3e91-a271-4832-bb68-19c60d535e46" />
<img width="887" height="685" alt="Disk Selection" src="https://github.com/user-attachments/assets/638bfa73-3053-44ce-8349-71338076cb25" />
<img width="887" height="685" alt="System Image Selection" src="https://github.com/user-attachments/assets/a1578c35-ed3f-4365-b348-18c4e11c1850" />
<img width="887" height="685" alt="Summary Page" src="https://github.com/user-attachments/assets/5a947148-0569-4e23-983c-961922dce0d2" />
<img width="887" height="685" alt="Installation (test-mode)" src="https://github.com/user-attachments/assets/f83fa1b7-e497-44c2-9020-696283fd6ac3" />
<img width="887" height="685" alt="Finished Page" src="https://github.com/user-attachments/assets/184ba7c4-5d75-4b70-862f-41ca35bd8604" />
<img width="887" height="685" alt="Finished Page w/ logs dialog" src="https://github.com/user-attachments/assets/355b5ddb-7108-4fdd-a83c-66430a9a7174" />


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

## Test Mode
There's also the **Test Mode** which you can simulate installation, without touch any of your drives. Kinda like dry-run..
To use test mode, just launch the installer with the `--test` command-line argument.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
