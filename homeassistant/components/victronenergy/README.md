# Victron Energy Integration

The Victron Energy integration allows you to connect your Victron Energy devices (such as solar charge controllers, battery monitors, and inverters) to Home Assistant via MQTT (through the use of a Venus OS device acting as a gateway)

## Supported Devices

This integration supports Victron Energy devices that have:
- Built-in MQTT capabilities (Cerbo GX, Venus GX, etc.)
- Home Assistant MQTT discovery enabled
- Network connectivity (Ethernet, Wi-Fi, or cellular)

Common supported devices include:
- Cerbo GX
- Ekrano GX
- Any GX device supporting v3.70 and up.
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

2. **MQTT is enabled on your Victron device (for Venus OS version ..TBD.. and lower)**:
   - Access your device's web interface
   - Navigate to Settings > Integrations and enable MQTT Access
   - Note the IP address of your device

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

1. **Enter Device Information (only for manual setup)**:
   - **Host**: Enter the IP address or hostname of your Victron Energy device
   - Example: `192.168.1.100` or `venus.local`

2. **Enter password**:
   - You'll always be prompted for a password, but if your Local Network Security Profile is set to Unsecured, this can be left empty.

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

### Local Network Security Profile
- The integration always connects to the MQTT broker on the GX Device using TLS and port 8883
- The MQTT connection always uses authenticates using a token that is generated during the configuration step
- To generate this token, the GX Password is necessary when the Local Network Security Profile is set to Secure or Weak. When the Local Network Security Profile is set to Unsecured, the password can be left empty

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
- **Firewall Issues**: Ensure port 8883 is not blocked
- **Device Settings**: Confirm MQTT services are running on the device

### Authentication Failed  
- Verify the secure profile password is correct
- Check MQTT user credentials in device settings
- Ensure the Local Network Security Profile is properly configured on the device

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

## Removing the Integration

To remove the Victron Energy integration from Home Assistant:

1. **Remove via UI**: 
   - Go to **Settings** > **Devices & Services**
   - Find the **Victron Energy** integration
   - Click the three-dot menu and select **Delete**
   - Confirm removal when prompted

2. **Alternative method via device**:
   - Go to **Settings** > **Devices & Services** > **Devices**
   - Find your Victron device
   - Click the device name, then click **Delete Device**
   - This will remove the device and all associated entities

All entities and device data will be permanently removed from Home Assistant. The integration can be re-added later if needed.

## Removal

To remove the Victron Energy integration:

1. Go to **Settings** > **Devices & Services**
2. Find the **Victron Energy** integration
3. Click the **three dots menu** (⋯) next to the integration
4. Select **Delete**
5. Confirm the deletion

All entities and devices associated with the integration will be removed from Home Assistant.