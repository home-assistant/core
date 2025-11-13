# Home Assistant Getting Started Guide

## Welcome to Home Assistant!

Home Assistant is an open-source home automation platform that prioritizes local control and privacy. This guide will help you get started with your Home Assistant installation.

## System Requirements

- Supported OS: Linux, Windows, macOS, or Raspberry Pi OS
- Minimum RAM: 2GB (4GB recommended)
- Python 3.9 or later
- Network connection for initial setup

## Installation Methods

### 1. Home Assistant Operating System (Recommended)

The easiest way to install Home Assistant:

```
- Download Home Assistant OS image
- Flash to USB drive or SD card using Balena Etcher
- Boot from the installation media
- Follow the on-screen setup wizard
```

### 2. Docker Installation

```bash
docker run -d --name homeassistant -e TZ=America/New_York -v homeassistant:/config -v /run/dbus:/run/dbus:ro --net=host ghcr.io/home-assistant/home-assistant:latest
```

### 3. Python Virtual Environment

```bash
python -m venv ha-env
source ha-env/bin/activate  # On Windows: ha-env\Scripts\activate
pip install homeassistant
hass --open-ui
```

## Initial Setup

1. **Access Home Assistant UI**: Navigate to http://localhost:8123
2. **Create Admin Account**: Set username and password
3. **Name Your Installation**: Choose a name for your Home Assistant instance
4. **Location Settings**: Set your location for weather and geolocation

## Essential Integrations

- **Automation**: Create automatons for home actions
- **MQTT**: Connect smart devices via MQTT broker
- **Google Cast**: Stream audio and video to devices
- **Z-Wave/Zigbee**: Wireless device protocols
- **REST/API**: Custom integrations via REST calls

## Adding Devices

1. Go to Settings > Devices & Services
2. Click "Create Automation" or "Add Integration"
3. Follow the integration-specific setup wizard
4. Test device discovery and connection

## Basic Automation Examples

### Turn on lights at sunset:
```yaml
automation:
  - alias: "Turn on lights at sunset"
    trigger:
      platform: sun
      event: sunset
    action:
      service: light.turn_on
      target:
        entity_id: light.living_room
```

## Troubleshooting

- **Cannot access UI**: Check firewall rules and network connectivity
- **Device not discovered**: Verify device is powered and on same network
- **Slow performance**: Monitor disk space and available RAM

## Resources

- Official Documentation: https://www.home-assistant.io/docs/
- Community Forum: https://community.home-assistant.io/
- GitHub Repository: https://github.com/home-assistant/core
