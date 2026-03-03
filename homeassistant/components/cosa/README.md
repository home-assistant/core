# Cosa integration for Home Assistant

The Cosa integration connects your [Cosa smart thermostats](https://www.cosa.com.tr) to Home Assistant, allowing you to monitor and control your heating system through the Cosa cloud service.

## Supported devices

- Cosa smart thermostats

## Features

### Climate entity

Each Cosa thermostat is exposed as a climate entity with the following capabilities:

#### Monitoring

- **Current temperature**: Displays the room temperature reported by the thermostat sensor.
- **Target temperature**: Shows the active target temperature based on the current operating mode.
- **HVAC action**: Indicates whether the thermostat is actively heating, idle, or off.

#### HVAC modes

| HVAC mode | Description |
|---|---|
| **Off** | Thermostat is disabled (frozen mode). No heating is performed. |
| **Heat** | Manual heating mode with a custom target temperature. |
| **Auto** | Schedule mode. The thermostat follows a predefined schedule configured in the Cosa app. |

#### Controls

- **Set target temperature**: Adjust the target temperature between 5°C and 35°C in 1°C steps. When a temperature is set, the thermostat automatically switches to manual (heat) mode.
- **Set HVAC mode**: Switch between off, heat, and auto modes.
- **Turn on / Turn off**: Quickly toggle the thermostat between heat mode and off.

## Configuration

The integration is configured through the Home Assistant UI.

1. Go to **Settings** > **Devices & services** > **Add integration**.
2. Search for **Cosa**.
3. Enter the email address and password for your Cosa account.

All thermostats linked to your account are automatically discovered and added.

## Data updates

The integration polls the Cosa cloud API every **3 minutes** for the latest thermostat data. Commands (mode changes, temperature adjustments) are sent immediately and trigger an instant data refresh.

## Known limitations

- Temperature values are integers (1°C steps) as defined by the Cosa API.
- Schedule configuration is not supported through Home Assistant — use the Cosa mobile app to manage schedules.
- The integration requires an active internet connection to communicate with the Cosa cloud service.
