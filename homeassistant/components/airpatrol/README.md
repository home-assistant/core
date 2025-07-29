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

### Sensor Issues
- If sensors show "unavailable", try reloading the integration
- Check that your AirPatrol units are properly configured and online
