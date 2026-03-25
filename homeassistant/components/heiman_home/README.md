# Heiman Home Integration for Home Assistant

## Overview

Heiman Cloud Home Assistant custom integration for connecting to the Heiman smart home platform, enabling device management, status monitoring, and control.

![Version](https://img.shields.io/badge/version-0.2.1-blue)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2023.1+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Supported Devices](#supported-devices)
- [Supported Languages](#supported-languages)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Services](#services)
- [API Reference](#api-reference)
- [Automation Examples](#automation-examples)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Cloud & Local Control**: Supports both Heiman Cloud API and local MQTT control
- **Multi-Home Support**: Manage devices across multiple homes
- **Real-time Updates**: MQTT-based real-time device status updates
- **Device Filtering**: Advanced filtering options for rooms, device types, and models
- **Area Synchronization**: Automatically sync room names to Home Assistant areas
- **Multi-Language Support**: 12 languages supported
- **Entity Management**: Automatic entity creation with customizable display options
- **Firmware Updates**: Built-in firmware update detection
- **Low Resource Usage**: Optimized polling intervals and efficient data synchronization

## Project Structure

```
heiman_home/
├── __init__.py              # Integration entry point
├── manifest.json            # Integration manifest
├── strings.json             # Translation strings (English)
├── const.py                 # Constants and configuration
├── config_flow.py           # Configuration flow UI
├── services.yaml            # Service definitions
├── diagnostics.py           # Diagnostic information
│
├── Core Modules
│   ├── heiman_cloud.py      # HTTP API client
│   ├── heiman_mqtt.py       # MQTT client
│   ├── heiman_device.py     # Device abstraction layer
│   ├── heiman_coordinator.py # Data coordinator
│   ├── heiman_storage.py    # Persistent storage
│   ├── heiman_error.py      # Error definitions
│   ├── heiman_i18n.py       # Internationalization
│   └── common.py            # Utility functions
│
├── Entity Platforms
│   ├── sensor.py            # Sensor entities
│   ├── binary_sensor.py     # Binary sensor entities
│   ├── switch.py            # Switch entities
│   ├── climate.py           # Climate control entities
│   ├── button.py            # Button entities
│   ├── cover.py             # Cover entities
│   ├── light.py             # Light entities
│   ├── fan.py               # Fan entities
│   ├── humidifier.py        # Humidifier entities
│   ├── number.py            # Number entities
│   ├── select.py            # Select entities
│   ├── text.py              # Text entities
│   └── update.py            # Update entities
│
└── translations/
    ├── de.json              # German
    ├── en.json              # English
    ├── es.json              # Spanish
    ├── fr.json              # French
    ├── it.json              # Italian
    ├── ja.json              # Japanese
    ├── nl.json              # Dutch
    ├── pt.json              # Portuguese
    ├── pt-BR.json           # Portuguese (Brazil)
    ├── ru.json              # Russian
    ├── tr.json              # Turkish
    ├── zh-Hans.json         # Chinese (Simplified)
    └── zh-Hant.json         # Chinese (Traditional)
```

## Supported Devices

| Device Type | Platform | Description |
|-------------|----------|-------------|
| Temperature Sensor | Sensor | Temperature monitoring |
| Humidity Sensor | Sensor | Humidity monitoring |
| Smoke Detector | Binary Sensor | Smoke detection |
| Motion Sensor | Binary Sensor | Motion detection |
| Door/Window Sensor | Binary Sensor | Open/close state |
| Water Leak Sensor | Binary Sensor | Water leak detection |
| CO Sensor | Binary Sensor | Carbon monoxide detection |
| Smart Switch | Switch | Power control |
| Smart Plug | Switch | Socket control |
| Smart Gateway | Hub | Gateway device |
| IPC Camera | Camera | Network camera |
| Smart Lock | Lock | Door lock control |
| Curtain Controller | Cover | Curtain/blind control |
| RGB Light | Light | Color lighting |
| Thermostat | Climate | Temperature control |
| Air Quality Sensor | Sensor | Air quality monitoring |
| Vibration Sensor | Binary Sensor | Vibration detection |
| Emergency Button | Button | SOS/Panic button |

## Supported Languages

This integration supports the following languages:

- ✅ **Chinese Simplified** (zh-Hans) - 简体中文
- ✅ **Chinese Traditional** (zh-Hant) - 繁體中文
- ✅ **English** (en)
- ✅ **German** (de) - Deutsch
- ✅ **French** (fr) - Français
- ✅ **Spanish** (es) - Español
- ✅ **Italian** (it) - Italiano
- ✅ **Japanese** (ja) - 日本語
- ✅ **Dutch** (nl) - Nederlands
- ✅ **Portuguese** (pt) - Português
- ✅ **Portuguese Brazil** (pt-BR) - Português (Brasil)
- ✅ **Russian** (ru) - Русский
- ✅ **Turkish** (tr) - Türkçe

## Installation

### Method 1: HACS (Recommended)

1. Open **HACS** in Home Assistant
2. Click on **Integrations**
3. Search for "Heiman Home"
4. Click **Download**
5. Restart Home Assistant

### Method 2: Manual Installation

1. Copy the `heiman_home` folder to your Home Assistant's `custom_components` directory:
   ```bash
   cp -r heiman_home /config/custom_components/
   ```

2. Restart Home Assistant:
   ```bash
   # If running Docker
   docker restart homeassistant
   ```

3. Add the integration via UI (see [Configuration](#configuration))

### Prerequisites

- Home Assistant 2023.1 or newer
- Python 3.9+
- Internet connection for cloud features
- MQTT broker (optional, for local control)

## Configuration

### Adding the Integration

1. Navigate to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "**Heiman Home**"
4. Click to add

### Configuration Steps

#### Step 1: Risk Notice
- Read the risk disclosure statement
- Check the box to accept the risks
- Click **Next**

#### Step 2: Authentication Configuration
- **Region**: Select your account region (Europe, China Mainland, Test Environment)
- **Language**: Choose the integration language
- **OAuth Redirect URL**: Configure if needed (default: `http://homeassistant.local:8123`)
- Click **Next**

#### Step 3: OAuth Login
- Click the login link
- Complete authentication in your browser
- Wait for automatic redirect

#### Step 4: Select Homes
- Choose which homes to import devices from
- You can select multiple homes
- Set room name synchronization mode:
  - **Don't Sync**: No area synchronization
  - **Room Name**: Use room names as areas
  - **Home Name**: Use home names as areas
  - **Home + Room**: Combine home and room names

#### Step 5: Device Filtering (Optional)
- Configure device filters by:
  - Room
  - Device type
  - Model
  - Specific devices
- Choose include/exclude mode

#### Step 6: Advanced Settings (Optional)
- **Hide Non-Standard Entities**: Hide unsupported entity types
- **Action Debug Mode**: Enable debug logging for actions
- **Binary Sensor Display**: Choose between boolean or enum mode

## Usage

### Device Management

All discovered devices will be automatically added to Home Assistant with:
- Proper entity naming
- Area assignment (if configured)
- Device information (model, firmware, connections)

### Entity Types

The integration creates entities based on device capabilities:

- **Sensors**: Temperature, humidity, air quality, battery level, etc.
- **Binary Sensors**: Motion, smoke, water leak, contact, vibration
- **Switches**: Lights, plugs, relays
- **Covers**: Curtains, blinds, garage doors
- **Climate**: Thermostats, HVAC controllers
- **Lights**: RGB lights, dimmable lights
- **Buttons**: Scene triggers, emergency buttons
- **Updates**: Firmware update notifications

### Viewing Device Information

1. Go to **Settings** → **Devices & Services**
2. Find your Heiman device
3. Click on the device to see:
   - Model information
   - Firmware version
   - Signal strength (RSSI)
   - Battery level
   - Last activity timestamp

## Services

The integration provides several services for advanced control:

### `heiman_home.refresh_devices`

Refresh the device list from the cloud.

**Service Data:**
```yaml
service: heiman_home.refresh_devices
data:
  entry_id: "abc123"  # Config entry ID
```

### `heiman_home.read_property`

Read a specific device property.

**Service Data:**
```yaml
service: heiman_home.read_property
data:
  entry_id: "abc123"
  device_id: "device123"
  property_name: "temperature"
```

### `heiman_home.write_property`

Write a value to a device property.

**Service Data:**
```yaml
service: heiman_home.write_property
data:
  entry_id: "abc123"
  device_id: "device123"
  property_name: "switch_status"
  value: true
```

### `heiman_home.sync_child_devices`

Sync child devices for gateway/sub-device setups.

**Service Data:**
```yaml
service: heiman_home.sync_child_devices
data:
  entry_id: "abc123"
  gateway_device_id: "gateway123"
```

## API Reference

### HTTP API Endpoints

#### Login
```http
POST /api-app/login
Content-Type: application/json

{
    "userName": "email@example.com",
    "password": "password"
}
```

**Response:**
```json
{
    "code": 0,
    "data": {
        "userId": "user_id",
        "accessToken": "access_token",
        "refreshToken": "refresh_token"
    }
}
```

#### Get Home List
```http
POST /api-app/homeUserRelation/get/homeList
Authorization: Bearer {access_token}
Content-Type: application/json

{
    "userId": "user_id"
}
```

#### Get Device List
```http
POST /api-app/device/get/listByHomeId
Authorization: Bearer {access_token}
Content-Type: application/json

{
    "homeId": "home_id"
}
```

#### Read Device Property
```http
POST /api-app/device/read/property
Authorization: Bearer {access_token}
Content-Type: application/json

{
    "deviceId": "device_id",
    "propertyName": "property_name"
}
```

### MQTT Topics

#### Read Property
```
Topic: /{product_id}/{device_id}/properties/read
Payload: { "property_id": "temperature" }
```

#### Write Property
```
Topic: /{product_id}/{device_id}/properties/write
Payload: { "property_id": "switch_status", "value": true }
```

#### Property Report
```
Topic: /{product_id}/{device_id}/properties/report
Payload: { "properties": { "temperature": 25.5, "humidity": 60 } }
```

#### Read/Write Reply
```
Topic: /{product_id}/{device_id}/properties/read/reply
Topic: /{product_id}/{device_id}/properties/write/reply
```

## Automation Examples

### Smoke Alarm Notification

Automatically send notifications when smoke is detected.

```yaml
automation:
  - alias: "Smoke Alarm Notification"
    trigger:
      - platform: state
        entity_id: binary_sensor.heiman_smoke_detector_smoke
        to: "on"
    action:
      - service: notify.mobile_app_my_phone
        data:
          message: "🚨 Smoke detected!"
          title: "Safety Alert"
```

### High Temperature Alert

Send alerts when temperature exceeds a threshold.

```yaml
automation:
  - alias: "High Temperature Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.heiman_temp_temperature
        above: 30
    action:
      - service: notify.mobile_app_my_phone
        data:
          message: "High temperature detected: {{ states('sensor.heiman_temp_temperature') }}°C"
```

### Auto Turn Off Lights at Night

Automatically turn off lights at 10 PM.

```yaml
automation:
  - alias: "Turn Off Lights at 10 PM"
    trigger:
      - platform: time
        at: "22:00:00"
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.heiman_lamp_power
```

### Water Leak Emergency Response

Shut off water valve when leak is detected.

```yaml
automation:
  - alias: "Water Leak Emergency Shutoff"
    trigger:
      - platform: state
        entity_id: binary_sensor.heiman_water_leak_detected
        to: "on"
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.heiman_water_valve
      - service: notify.mobile_app_my_phone
        data:
          message: "💧 Water leak detected! Valve has been closed."
```

### Motion-Activated Lighting

Turn on lights when motion is detected at night.

```yaml
automation:
  - alias: "Motion-Activated Night Light"
    trigger:
      - platform: state
        entity_id: binary_sensor.heiman_motion_detected
        to: "on"
    condition:
      - condition: sun
        after sunset
      - condition: state
        entity_id: switch.heiman_night_light
        state: "off"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.heiman_night_light
```

## Troubleshooting

### Enable Debug Logging

Add to `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    heiman_home: debug
```

Then restart Home Assistant and check logs:

```bash
# View logs
tail -f /config/home-assistant.log | grep heiman_home
```

### Common Issues

#### Q: Cannot connect to Heiman Cloud

**Solutions:**
- Check network connectivity
- Verify the selected region matches your account
- Check firewall settings
- Ensure ports 443 (HTTPS) and 1883/1884 (MQTT) are open

#### Q: Device status not updating

**Solutions:**
- Check MQTT connection status in logs
- Verify device is online and connected
- Try refreshing devices via service call
- Restart Home Assistant

#### Q: Authentication failed

**Solutions:**
- Verify email and password are correct
- Clear integration and reconfigure
- Check if account is locked
- Ensure OAuth redirect URL is accessible

#### Q: Some devices not showing up

**Solutions:**
- Check device filter settings
- Verify device is assigned to a selected home
- Check if device type is supported
- Review debug logs for errors

#### Q: Entities showing as unavailable

**Solutions:**
- Check device battery level
- Verify device is within range of gateway
- Check gateway connectivity
- Try re-adding the device

### Download Diagnostics

1. Go to **Settings** → **Devices & Services**
2. Select **Heiman Home** integration
3. Click **⋮** (menu) → **Download Diagnostics**
4. Review the JSON file or share with support

## Development

### Adding New Entity Types

1. Create entity class in the appropriate platform file (e.g., `sensor.py`)
2. Add property mapping in `heiman_device.py`
3. Add platform to `PLATFORMS` list in `const.py`
4. Add translations in `strings.json` and translation files

Example:

```python
# In sensor.py
class HeimanAirQualitySensor(HeimanSensorEntity):
    """Air quality sensor entity."""
    
    def __init__(self, device, coordinator):
        super().__init__(device, coordinator)
        self._attr_native_unit_of_measurement = "μg/m³"
        self._attr_device_class = "aqi"
```

### Adding New Language Support

1. Add language to `INTEGRATION_LANGUAGES` in `const.py`
2. Create translation file in `translations/` directory
3. Update `heiman_i18n.py` with translation dictionaries

Example translation file structure:

```json
{
    "config": {
        "step": {
            "auth_config": {
                "title": "Authentication Configuration"
            }
        }
    },
    "entity": {
        "sensor": {
            "temperature": {
                "name": "Temperature"
            }
        }
    }
}
```

### Testing Locally

1. Clone the repository:
   ```bash
   git clone https://github.com/Leo2442926161/heiman_home.git
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run tests:
   ```bash
   pytest test/
   ```

## Contributing

We welcome contributions! Here's how you can help:

### Reporting Issues

- Use GitHub Issues to report bugs
- Include debug logs and diagnostics
- Describe steps to reproduce

### Submitting Pull Requests

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

### Translation Contributions

If you want to add or improve translations:

1. Update the corresponding `translations/*.json` file
2. Test in your Home Assistant instance
3. Submit a pull request with your changes

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.

**Disclaimer**: This integration is for educational purposes only. Use it at your own risk. Heiman Cloud API is property of Heiman Technology Co., Ltd.

## Acknowledgments

- **Heiman Technology** for providing the cloud platform
- **Home Assistant Community** for excellent documentation and support
- All contributors who have helped with this integration

## Support

- **Documentation**: [GitHub Wiki](https://github.com/Leo2442926161/heiman_home/wiki)
- **Issues**: [GitHub Issues](https://github.com/Leo2442926161/heiman_home/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Leo2442926161/heiman_home/discussions)

---

**Made with ❤️ by the Heiman Home Integration Team**
