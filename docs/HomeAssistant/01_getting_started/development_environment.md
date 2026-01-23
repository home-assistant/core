# Set up development environment

You'll need to set up a development environment if you want to develop a new feature or component for Home Assistant. Read on to learn how to set up.

## Developing with Visual Studio Code + devcontainer
Follow our [devcontainer development environment guide](/docs/setup_devcontainer_environment) to set up a proper development environment first.

**Note:** As this approach uses containers, you may face challenges exposing hardware like USB devices & adapters (onboard Bluetooth, Zigbee, ...) into the container for testing. This is possible when developing on a Linux host; however, you cannot directly access such hardware if you are using a Windows or MacOS computer for development.

### Prerequisites
* Docker
* Visual Studio code
* Git

### Getting started
1. Go to [Home Assistant core repository](https://github.com/home-assistant/core) and click **Fork**.
2. Copy your fork's URL and paste it into VS Code to clone/open.
3. Your browser will prompt you if you want to use Visual Studio Code to open the link, click **Open Link**.
4. When Visual Studio Code asks if you want to install the Remote - SSH extension, click **Install**.
5. The dev container image will then be built (this may take a few minutes), after this your development environment will be ready.
6. You can verify that your dev container is set up properly by:
    * Opening the Command Palette: `Shift+Command+P` (Mac) / `Ctrl+Shift+P` (Windows/Linux)
    * Select `Tasks: Run Task` -> `Run Home Assistant Core`
    * Navigate to `http://localhost:8123` to see the setup screen.

### Tasks
The dev container comes with useful tasks (Shift+Command+P -> Tasks: Run Task) to help with development, such as running Home Assistant or restarting services.

### Debugging with Visual Studio Code
The dev container supports debugging by default. Press `F5` to launch Home Assistant with the debugger attached.

## Manual Environment
Use these instructions only if you do not want to use devcontainers. Python version 3.13 is required.

### Developing on Ubuntu / Debian
```bash
sudo apt-get update
sudo apt-get install python3-pip python3-dev python3-venv autoconf libssl-dev libxml2-dev libxslt1-dev libjpeg-dev libffi-dev libudev-dev zlib1g-dev pkg-config libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libswscale-dev libswresample-dev libavfilter-dev ffmpeg libgammu-dev build-essential
```

### Developing on Fedora
```bash
sudo dnf update
sudo dnf install python3-pip python3-devel python3-virtualenv autoconf openssl-devel libxml2-devel libxslt-devel libjpeg-turbo-devel libffi-devel systemd-devel zlib-devel pkgconf-pkg-config libavformat-free-devel libavcodec-free-devel libavdevice-free-devel libavutil-free-devel libswscale-free-devel ffmpeg-free-devel libavfilter-free-devel ffmpeg-free gcc gcc-c++ cmake
```

### Developing on Arch / Manjaro
```bash
sudo pacman -Sy base-devel python python-pip python-virtualenv autoconf libxml2 libxslt libjpeg-turbo libffi systemd zlib pkgconf ffmpeg gcc cmake
```

### Developing on Windows
Use WSL (Windows Subsystem for Linux) with Ubuntu. Follow the Linux instructions within the WSL terminal. Use `ip addr show eth0` to find the IP address if `localhost:8123` doesn't work.

### Developing on macOS
```bash
brew install python3 autoconf ffmpeg cmake make
```

### Setup Local Repository
```bash
git clone https://github.com/YOUR_GIT_USERNAME/core
cd core
git remote add upstream https://github.com/home-assistant/core.git
script/setup
source .venv/bin/activate
hass -c config
```