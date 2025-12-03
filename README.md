# ObsidianOS Installer

This repository contains the graphical installer for ObsidianOS, an A/B GNU/Linux distribution based on Arch. This installer is built using PySide6 and provides a user-friendly interface to guide you through the installation process. Comes with [ObsidianOS KDE](https://github.com/Obsidian-OS/archiso-plasma) and [ObsidianOS COSMIC](https://github.com/Obsidian-OS/archiso-cosmic).

## Screenshots
*Note: These colors and icons come from the KDE theme I'm using, doesn't represent how it looks in the ISO image*
<img width="933" height="957" alt="image" src="https://github.com/user-attachments/assets/a963000c-f2cf-441b-9c00-0dd45683a069" />
<img width="933" height="957" alt="image" src="https://github.com/user-attachments/assets/710679ee-d511-4274-ae7e-19c184cef94e" />
<img width="933" height="957" alt="image" src="https://github.com/user-attachments/assets/7f1c044a-4172-48c6-820d-37e522dcfed2" />
<img width="933" height="957" alt="image" src="https://github.com/user-attachments/assets/13df36d1-3800-4038-8793-cb663be70aff" />
<img width="933" height="957" alt="image" src="https://github.com/user-attachments/assets/4038266f-12d1-4c32-a011-7a84a149f4ce" />
<img width="933" height="957" alt="image" src="https://github.com/user-attachments/assets/850f0e12-8eb1-470a-8283-c7a201a09d30" />
<img width="933" height="957" alt="image" src="https://github.com/user-attachments/assets/866a62cc-e5e6-4dcc-9370-f387dec15e22" />
<img width="933" height="957" alt="image" src="https://github.com/user-attachments/assets/eacb01d0-e60f-4cfc-9dc3-2ad6b03e681e" />
<img width="935" height="956" alt="image" src="https://github.com/user-attachments/assets/021d9f47-a77b-4213-8b8c-5ad3d5d303c3" />
<img width="933" height="957" alt="image" src="https://github.com/user-attachments/assets/9ba98bb8-c4ec-4eae-a2db-900e578f44cf" />
<img width="933" height="957" alt="image" src="https://github.com/user-attachments/assets/cd1e4f92-58e5-4f1b-90d6-281a59dbac03" />
<img width="933" height="957" alt="image" src="https://github.com/user-attachments/assets/ee53622f-4616-480f-b11d-ccdff4da8079" />
<img width="933" height="957" alt="image" src="https://github.com/user-attachments/assets/a1bff842-cb22-4eb2-868a-b9420323e03d" />
<img width="933" height="957" alt="image" src="https://github.com/user-attachments/assets/66ecd4bb-0395-4c9b-b890-da7e7328dbfd" />



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
