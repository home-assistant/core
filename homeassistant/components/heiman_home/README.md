# Heiman Home Integration

The Heiman Home integration allows you to connect your Heiman smart home devices to Home Assistant. This integration uses OAuth2 authentication to securely access your Heiman Home account and provides real-time monitoring and control of your devices.

## Supported Devices

Heiman Home supports a wide range of smart home devices including:

- **Smoke Detectors** - Monitor smoke detection status
- **Carbon Monoxide Detectors** - Track CO levels and alarms
- **Water Leak Sensors** - Detect water leaks and flooding
- **Door/Window Sensors** - Monitor open/close status
- **Motion Sensors** - Detect movement in rooms
- **Temperature & Humidity Sensors** - Monitor environmental conditions
- **Smart Plugs & Switches** - Control power outlets remotely
- **Signal Strength Monitoring** - Track device connectivity

## Configuration

### Prerequisites

Before setting up the integration, ensure you have:

1. A Heiman Home account with registered devices
2. The Heiman Home app installed and configured on your mobile device
3. Your devices properly connected to your Heiman Home account

### Setup Steps

1. Navigate to **Settings** > **Devices & Services** in Home Assistant
2. Click the **+ Add Integration** button
3. Search for "Heiman Home" and select it
4. You will be redirected to the Heiman Home authorization page
5. Log in with your Heiman Home credentials
6. Grant the necessary permissions to Home Assistant
7. Select which homes (families) you want to import devices from
8. Choose how room names should be synchronized to Home Assistant areas:
   - **Do not sync** - Keep existing area assignments
   - **Room name** - Use Heiman room names
   - **Home name** - Use Heiman home names
   - **Home name and Room name** - Combine both (e.g., "Living Room - First Floor")
9. Click **Submit** to complete the setup

### Multi-Home Support

If you have multiple homes configured in your Heiman Home account, you can select which homes to import devices from. The integration supports importing devices from multiple homes simultaneously.

## Features

### Real-Time Updates

The integration uses MQTT for real-time device status updates, ensuring that device states are synchronized immediately when changes occur.

### Device Filtering

You can configure filters to include or exclude specific devices based on:
- Room/area
- Device type
- Device model
- Specific device IDs

### Area Synchronization

Device areas in Home Assistant can be automatically synchronized with your Heiman Home room structure based on your chosen synchronization mode.

## Services

The integration provides the following services:

### `heiman_home.read_device_properties`

Manually read properties from a specific Heiman device.

**Service Data:**

| Parameter | Description | Required | Example |
|-----------|-------------|----------|---------|
| `device_id` | The ID of the device to read properties from | Yes | `"1234567890abcdef"` |

**Example Usage:**

```yaml
service: heiman_home.read_device_properties
data:
  device_id: "1234567890abcdef"
```

This service is useful for troubleshooting or forcing a refresh of device properties when automatic updates are not working as expected.

## Entities

The integration creates various entities depending on your devices:

### Sensors

- **Temperature** - Current temperature readings (°C)
- **Humidity** - Current humidity levels (%)
- **Battery Level** - Device battery percentage (%)
- **Signal Strength** - WiFi signal strength (dBm)
- **Power Consumption** - Real-time power usage (W)
- **Energy Usage** - Total energy consumed (kWh)
- **CO Concentration** - Carbon monoxide levels (PPM)

### Binary Sensors

- **Smoke Detection** - Smoke alarm status
- **CO Alarm** - Carbon monoxide alarm status
- **Water Leak** - Water leak detection
- **Door/Window Status** - Open/closed state
- **Motion Detection** - Motion detected status
- **Tamper Alert** - Device tampering detection
- **Low Battery** - Battery level warning

### Switches

- **Light Control** - Turn lights on/off
- **Freezing Point Protection** - Enable/disable freeze protection
- **Buzzer Control** - Enable/disable device buzzer

### Buttons

- **Remote Locate** - Trigger device location sound
- **Remote Check** - Perform remote device check
- **Mute Alarm** - Silence active alarms

### Select

- **Alarm Sound Option** - Configure alarm sound pattern (Fast/Medium/Slow Beep)

## Troubleshooting

### Authentication Issues

If you experience authentication problems:

1. Go to **Settings** > **Devices & Services**
2. Find the Heiman Home integration
3. Click **Configure** to re-authenticate
4. Follow the OAuth2 flow again

### Devices Not Appearing

If your devices are not showing up:

1. Verify devices are online in the Heiman Home app
2. Check that you selected the correct home during setup
3. Review device filter settings if configured
4. Try using the `read_device_properties` service to force a refresh

### Connection Issues

For connectivity problems:

1. Ensure your Heiman devices have a stable internet connection
2. Check your Home Assistant instance has internet access
3. Verify the Heiman Home cloud service is operational
4. Review Home Assistant logs for error messages

## Technical Details

- **Integration Type:** Hub
- **IoT Class:** Cloud Polling with MQTT real-time updates
- **Authentication:** OAuth2
- **Dependencies:** `application_credentials`

## Support

For issues related to:

- **Home Assistant Integration:** Report issues on the Home Assistant GitHub repository
- **Heiman Devices:** Contact Heiman customer support
- **Heiman Cloud Service:** Visit the Heiman official website

## Additional Resources

- [Heiman Official Website](https://www.heiman.com)
- [Home Assistant Documentation](https://www.home-assistant.io/integrations/heiman_home)
- [Home Assistant Community Forum](https://community.home-assistant.io)
