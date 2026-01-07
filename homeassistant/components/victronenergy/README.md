# Victron Energy Integration

The Victron Energy integration allows you to connect your Victron Energy devices (such as solar charge controllers, battery monitors, and inverters) to Home Assistant via MQTT (through the use of a Venus OS device acting as a gateway)

## Supported Devices

This integration supports Victron Energy devices that have:
- Built-in MQTT capabilities (Cerbo GX, Venus GX, etc.)
- Home Assistant MQTT discovery enabled
- Network connectivity (Ethernet, Wi-Fi, or cellular)

Common supported devices include:
- Cerbo GX
- Venus GX  
- Ekrano GX
- MPPT Solar Charge Controllers
- BMV Battery Monitors
- MultiPlus Inverter/Chargers
- Phoenix Inverters

## Features

Once configured, this integration will automatically discover and add entities for:

- **Sensors**: Battery voltage, current, power, solar panel output, AC loads, etc.
- **Binary Sensors**: Alarm states, relay statuses
- **Switches**: Relay controls, inverter on/off
- **Number Controls**: Voltage limits, charge current limits

All discovered entities will appear in Home Assistant with appropriate device classes, units of measurement, and friendly names.

## Prerequisites

Before setting up this integration, ensure that:

1. **You have a Venus OS device running 3.70~61 or higher**

2. **MQTT is enabled on your Victron device**:
   - Access your device's web interface
   - Navigate to Settings > Services > MQTT
   - Enable "MQTT on LAN (Insecure)" or configure secure MQTT
   - Note the IP address of your device

3. **Home Assistant MQTT discovery is enabled**:
   - In your device's MQTT settings
   - Enable "Home Assistant MQTT discovery"
   - This allows automatic detection of available sensors and controls

## Installation

### Automatic Discovery

If your Victron Energy device supports SSDP (Service Discovery Protocol), it may be automatically discovered by Home Assistant:

1. Go to **Settings** > **Devices & Services**
2. Look for a discovered "Victron Energy" device
3. Click **Configure** and follow the setup wizard

### Manual Setup

If automatic discovery doesn't work:

1. Go to **Settings** > **Devices & Services**
2. Click **Add Integration**
3. Search for "Victron Energy"
4. Click on the integration to start setup

#### Setup Process

1. **Enter Device Information**:
   - **Host**: Enter the IP address or hostname of your Victron Energy device
   - Example: `192.168.1.100` or `venus.local`

2. **Authentication** (if required):
   - If using secure MQTT, you'll be prompted for the secure profile password
   - This is configured in your device's MQTT security settings

3. **Discovery**:
   - The integration will connect to your device and discover available entities
   - This process may take up to 30 seconds

4. **Completion**:
   - Once discovery is complete, your device and all discovered entities will be added to Home Assistant

## Configuration

### Device Settings

After setup, you can access device settings through:
- **Settings** > **Devices & Services** > **Victron Energy** > **Configure**

### Entity Management

- **Enable/Disable Entities**: Some diagnostic entities may be disabled by default to reduce clutter
- **Customize Names**: Entity names can be customized through the entity settings
- **Entity Categories**: Entities are automatically categorized (e.g., diagnostic entities)

## Security Considerations

### Unsecure MQTT
- The integration first attempts to connect using unsecure MQTT (port 1883)
- This is the default configuration for most Victron devices
- Data is transmitted in plain text on your local network

### Secure MQTT  
- If unsecure connection fails, you'll be prompted for the secure profile password
- Secure MQTT uses encryption and authentication
- Configure the secure profile password in your device's MQTT settings first

### Network Security
- Ensure your Victron device is only accessible on your trusted local network
- Consider using VLANs to isolate IoT devices if security is a concern
- Regularly update your device firmware for security patches

## Troubleshooting

### Device Not Discovered
- Verify MQTT is enabled on your Victron device
- Check that Home Assistant MQTT discovery is enabled in device settings
- Ensure the device is on the same network as Home Assistant
- Try manual setup using the device's IP address

### Connection Failed
- **Check Network Connectivity**: Verify the device IP address is correct and reachable
- **Firewall Issues**: Ensure ports 1883 (unsecure) or 8883 (secure) are not blocked
- **Device Settings**: Confirm MQTT services are running on the device

### Authentication Failed  
- Verify the secure profile password is correct
- Check MQTT user credentials in device settings
- Ensure secure MQTT is properly configured on the device

### No Entities Discovered
- Wait up to 30 seconds for discovery to complete
- Verify Home Assistant MQTT discovery is enabled on the device
- Check that the device has active sensors/controls to discover
- Restart the integration if discovery appears stuck

### Missing Entities
- Some entities may be disabled by default (especially diagnostic sensors)
- Check **Settings** > **Devices & Services** > **Victron Energy** > **Entities** 
- Enable desired entities manually

## Support

### Getting Help
- Check the [Home Assistant Community Forum](https://community.home-assistant.io/) for Victron Energy discussions
- Review Victron Energy documentation for device-specific MQTT configuration
- Consult your device manual for networking and MQTT setup instructions

### Reporting Issues
- Ensure you're running the latest Home Assistant version
- Include device model and firmware version when reporting issues
- Enable debug logging for the `victronenergy` component if requested

### Additional Resources
- [Victron Energy MQTT Documentation](https://www.victronenergy.com/live/venus_os:mqtt)
- [Home Assistant MQTT Integration](https://www.home-assistant.io/integrations/mqtt/)