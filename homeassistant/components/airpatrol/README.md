# AirPatrol

The AirPatrol integration allows you to integrate your AirPatrol devices with Home Assistant.

## Configuration

To add AirPatrol to your installation, go to **Configuration** >> **Integrations** in the UI, click the button with the `+` sign and from the list of integrations select **AirPatrol**.

## Installation

1. In Home Assistant, go to **Configuration** >> **Integrations**
2. Click the **+** button to add a new integration
3. Search for "AirPatrol"
4. Enter your AirPatrol username and password
5. Click **Submit**

## Features

### Sensors
- **Temperature**: Current room temperature from each AirPatrol unit
- **Humidity**: Current room humidity from each AirPatrol unit
- **Status**: Online/offline status of the integration

### Climate Control
Each AirPatrol unit provides a climate entity with the following features:
- **HVAC Modes**: Heat, Cool, and Off
- **Temperature Control**: Set target temperature (16°C - 30°C)
- **Fan Speed**: Low, Medium, and High fan speeds
- **Swing Mode**: On/Off swing control
- **Current Temperature**: Real-time room temperature display
- **HVAC Action**: Shows current heating/cooling action

### Climate Controls
- **Set Temperature**: Adjust the target temperature for heating/cooling
- **Change HVAC Mode**: Switch between heat, cool, and off modes
- **Adjust Fan Speed**: Control the fan speed (low, medium, high)
- **Toggle Swing**: Turn swing mode on or off
- **Turn On/Off**: Quick controls to turn the unit on or off

## Removal

To remove the AirPatrol integration:

1. Go to **Configuration** >> **Integrations**
2. Find the AirPatrol integration
3. Click on it and then click **Delete**
4. Confirm the deletion

## Reloading the Integration

To refresh device data and clear the pairings cache:

1. Go to **Configuration** >> **Integrations**
2. Find the AirPatrol integration
3. Click on it and then click **Reload**

This will force a fresh fetch of device data from the AirPatrol API.

## Troubleshooting

### Connection Issues
- Verify your AirPatrol credentials are correct
- Check your internet connection
- Ensure the AirPatrol service is available

### Climate Control Issues
- Make sure your AirPatrol unit supports the climate features you're trying to use
- Check that the unit is online and responding
- Try reloading the integration to refresh the connection

### Sensor Issues
- If sensors show "unavailable", try reloading the integration
- Check that your AirPatrol units are properly configured and online
