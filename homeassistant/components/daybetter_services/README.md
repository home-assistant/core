# DayBetter Services

![Supports a restart][restart-shield]
![Quality Scale][quality-scale]
![Integration Type][integration-type]

This integration allows you to control DayBetter smart lights and switches through the DayBetter Cloud API in Home Assistant. It provides cloud-based device control with real-time status updates via MQTT.

## Features

### Supported Devices
- **Smart Lights**: Full RGB color control, brightness adjustment, and color temperature control
- **Smart Switches**: On/off control with status monitoring
- **Smart Sensors**: Temperature and humidity monitoring with real-time data updates

### Supported Functions
- **Light Control**:
  - Turn lights on/off
  - Adjust brightness (0-255)
  - Set color temperature (Kelvin)
  - Set RGB/HS color values
  - Real-time status updates via MQTT
  
- **Switch Control**:
  - Turn switches on/off
  - Real-time status updates via MQTT

- **Sensor Monitoring**:
  - Temperature readings (Fahrenheit)
  - Humidity readings (percentage)
  - Real-time data updates via MQTT
  - Historical data logging

### Integration Features
- **Config Flow**: Easy setup through the UI
- **Cloud Polling**: Periodic device status updates
- **MQTT Integration**: Real-time device status updates
- **Service Calls**: Manual device refresh and MQTT reconnection
- **Error Handling**: Comprehensive error handling and logging

## Installation

### Prerequisites
- Home Assistant 2023.1.0 or later
- Valid DayBetter user code for API authentication
- Internet connection for cloud API access

### Setup Steps

1. **Add Integration**:
   - Go to **Settings** > **Devices & Services**
   - Click **Add Integration**
   - Search for "DayBetter Services"
   - Click on the integration

2. **Configuration**:
   - Enter your DayBetter user code
   - The integration will authenticate with the DayBetter API
   - Upon successful authentication, your devices will be discovered automatically

3. **Verification**:
   - Check that your devices appear in **Settings** > **Devices & Services**
   - Verify device entities are created in **Settings** > **Entities**

## Configuration Parameters

| Parameter | Description | Required | Default |
|-----------|-------------|----------|---------|
| `user_code` | Your DayBetter user code for API authentication | Yes | - |
| `token` | API authentication token (auto-generated) | No | Auto-generated |

## Service Calls

The integration provides several service calls for advanced control:

### `daybetter_services.refresh_devices`
Refresh the device list from the DayBetter API.

**Service Data**: None

**Example**:
```yaml
service: daybetter_services.refresh_devices
```

### `daybetter_services.trigger_mqtt_connection`
Manually trigger MQTT reconnection.

**Service Data**: None

**Example**:
```yaml
service: daybetter_services.trigger_mqtt_connection
```

## Integration Details

- **Domain**: `daybetter_services`
- **IoT Class**: `cloud_polling`
- **Supported Platforms**: `light`, `switch`, `sensor`
- **API Base URL**: `https://a.dbiot.org/daybetter/hass/api/v1.0/`
- **MQTT Support**: Yes (for real-time updates)

## Device Support

### Supported Device Types
- **Smart Lights**: RGB and color temperature control
- **Smart Switches**: On/off functionality
- **Smart Sensors**: Temperature and humidity monitoring

### Supported Device PIDs

#### Smart Lights
- **P032**
- **P041**
- **P042**
- **P048**
- **P04F**
- **P051**
- **P056**
- **P059**
- **P05F**
- **P074**
- **P076**
- **P079**
- **P07A**
- **P08B**

#### Smart Switches
- **P033**
- **P047**
- **P052**

#### Smart Sensors
- **P075**

### Device Compatibility Check

To verify if your DayBetter device is supported by this integration:

1. **Check Device PID**: Look for the PID (Product ID) on your device or in the DayBetter app
2. **Compare with Supported List**: Ensure your device's PID is listed above
3. **Total Supported Models**: 18 different device models across 3 categories

**Supported PID Summary**:
- **Lights**: P032, P041, P042, P048, P04F, P051, P056, P059, P05F, P074, P076, P079, P07A, P08B
- **Switches**: P033, P047, P052  
- **Sensors**: P075

### Device Attributes
- **Lights**:
  - `brightness`: 0-255
  - `color_temp_kelvin`: Color temperature in Kelvin
  - `hs_color`: Hue and saturation values
  - `is_on`: Device state
  
- **Switches**:
  - `is_on`: Device state

- **Sensors**:
  - `temperature`: Temperature reading in Fahrenheit
  - `humidity`: Humidity reading as percentage
  - `unit_of_measurement`: °F for temperature, % for humidity

## Known Limitations

1. **Cloud Dependency**: This integration requires internet connectivity
2. **API Rate Limits**: Respects DayBetter API rate limiting
3. **MQTT Optional**: Integration works without MQTT, but real-time updates require MQTT connection
4. **Device Discovery**: Only devices associated with your user code will be discovered
5. **Temperature Units**: Temperature sensors automatically convert from Celsius (received via MQTT) to Fahrenheit for display

## Troubleshooting

### Common Issues

#### Authentication Failed
**Symptoms**: Integration setup fails with "Authentication failed" error
**Solutions**:
- Verify your DayBetter user code is correct
- Check that your user code is active and not expired
- Ensure you have internet connectivity

#### Devices Not Appearing
**Symptoms**: Integration loads but no devices are discovered
**Solutions**:
- Call the `daybetter_services.refresh_devices` service
- Check Home Assistant logs for API errors
- Verify devices are associated with your user code in the DayBetter app

#### MQTT Connection Issues
**Symptoms**: Devices work but real-time updates are not working
**Solutions**:
- Call the `daybetter_services.trigger_mqtt_connection` service
- Check Home Assistant logs for MQTT connection errors
- Verify network connectivity to MQTT broker

#### Device Control Not Working
**Symptoms**: Devices appear but control commands don't work
**Solutions**:
- Check device online status in the DayBetter app
- Verify API token is valid (try reconfiguring the integration)
- Check Home Assistant logs for control errors

#### Sensor Data Not Updating
**Symptoms**: Sensors appear but temperature/humidity readings are not updating
**Solutions**:
- Check MQTT connection status (sensors rely on MQTT for real-time updates)
- Verify sensor is online in the DayBetter app
- Call the `daybetter_services.trigger_mqtt_connection` service to reconnect
- Check Home Assistant logs for MQTT message processing errors

#### Unsupported Device
**Symptoms**: Device appears in DayBetter app but not discovered by integration
**Solutions**:
- Check if your device PID is in the supported list above
- Verify device PID in DayBetter app (Settings > Device Info)
- Currently supported PIDs: Lights (P032, P041, P042, P048, P04F, P051, P056, P059, P05F, P074, P076, P079, P07A, P08B), Switches (P033, P047, P052), Sensors (P075)
- If your device PID is not listed, it may not be supported yet

### Debugging

Enable debug logging to troubleshoot issues:

```yaml
logger:
  logs:
    homeassistant.components.daybetter_services: debug
```

### Log Analysis

Look for these log patterns:
- `DayBetter auth OK`: Successful authentication
- `Failed to fetch devices`: API communication issues
- `MQTT connection failed`: MQTT connectivity problems
- `Device control failed`: Control command issues
- `Sensor data received`: Successful sensor data processing
- `Failed to process sensor data`: Sensor data parsing issues

## Use Cases

### Home Automation
- Integrate DayBetter devices into Home Assistant automations
- Use device states as triggers for other automations
- Control multiple devices simultaneously

### Scenes and Scripts
- Create scenes that control multiple DayBetter devices
- Use scripts for complex lighting sequences
- Implement lighting schedules and timers

### Energy Monitoring
- Monitor device usage patterns
- Create energy-saving automations
- Track device status and uptime

### Environmental Monitoring
- Monitor temperature and humidity in different rooms
- Create climate-based automations
- Set up alerts for temperature/humidity thresholds
- Track environmental trends over time

## Support

For issues and feature requests:
1. Check this documentation first
2. Review Home Assistant logs
3. Test with the troubleshooting steps above
4. Report issues with detailed logs and device information

## Changelog

### Version 1.0.0
- Initial release
- Smart light support with RGB and color temperature control (14 models: P032, P041, P042, P048, P04F, P051, P056, P059, P05F, P074, P076, P079, P07A, P08B)
- Smart switch support with on/off control (3 models: P033, P047, P052)
- Smart sensor support with temperature and humidity monitoring (1 model: P075)
- Cloud API integration
- MQTT support for real-time updates
- Config flow setup
- Comprehensive error handling and logging
- Temperature unit conversion (Celsius to Fahrenheit)

---

[restart-shield]: https://img.shields.io/badge/restart-no-red.svg
[quality-scale]: https://img.shields.io/badge/quality%20scale-bronze-yellow.svg
[integration-type]: https://img.shields.io/badge/integration%20type-hub-blue.svg