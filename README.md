# DCS GunCam

DCS World GunCam recording application for capturing your best moments in DCS World.

## Features

- Automatic recording when firing weapons
- Multiple trigger support (Gun, Canon, Bombs/Rockets)
- Pre-recording buffer to capture moments before trigger pull
- Customizable recording duration
- Modern and intuitive interface
- High-quality video output (up to 4K)

## System Requirements

- Windows 10 or 11
- Python 3.8 or higher
- 4GB RAM minimum (8GB recommended)
- DirectX 11 compatible graphics card
- DCS World installed
- 1GB free disk space for installation
- Additional disk space for recordings

## Quick Installation

1. Download and install Python 3.x from [python.org](https://www.python.org/downloads/)
   - Make sure to check "Add Python to PATH" during installation
2. Download the latest release of DCS GunCam
3. Extract the files to a location of your choice
4. Run `install.bat` as administrator
5. Start DCS World
6. Run `start.bat` to launch DCS GunCam

## Manual Installation

If the automatic installation fails, you can install the required packages manually:

```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

## First Time Setup

1. Launch DCS GunCam using `start.bat`
2. Configure your trigger buttons:
   - Click each trigger button
   - Press the corresponding button on your joystick
3. Set your pilot name and unit
4. Adjust recording settings if desired:
   - Buffer time (pre-recording duration)
   - Post-trigger time
   - Video quality
   - Frame rate

## Usage

1. Start DCS World
2. Launch DCS GunCam
3. The application will automatically detect DCS World
4. When you fire your weapons:
   - Recording starts automatically
   - A red dot indicates active recording
   - Recording continues for the set duration after releasing the trigger
   - Videos are saved to `C:\Users\Public\Videos\DCS_GunCam`

## Troubleshooting

If you encounter issues:

1. Check if Python is installed correctly
2. Run `install.bat` as administrator
3. Check the log file (`guncam.log`) for error messages
4. Make sure all required packages are installed
5. Verify DCS World is running before starting DCS GunCam

## Support

For support, updates, and documentation:
- Visit [ProtoDutch.com](https://www.protodutch.com)
- Check the [GitHub Issues](https://github.com/ProtoDutch/DCS_GunCam/issues)
- Create a new issue if your problem isn't listed

## License

This project is licensed under the MIT License. See the LICENSE file for details.