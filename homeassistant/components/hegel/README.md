# Home Assistant – Hegel Amplifier

The Hegel integration allows you to control and monitor supported Hegel amplifiers directly from Home Assistant.
It uses Hegel’s official IP control protocol over TCP and supports real-time push updates for a responsive experience.

## Supported Devices

- H95
- H120
- H190
- H190V
- H390
- H590

Other Hegel models with the same IP control protocol may also work.

## Features

- Power on/off
- Volume up / down / set (with native push feedback)
- Mute toggle
- Source selection
- State restoration on reconnect
- Automatic reconnect with exponential backoff
- Background slow poll (for resiliency if push updates are missed)

## Configuration

This integration is set up via the Home Assistant UI:

1. Navigate to Settings → Devices & Services.
2. Click Add Integration and search for Hegel.
3. Enter the amplifier’s host (IP address).
4. Home Assistant will automatically discover the model, serial number, and UDN from the device.

No YAML configuration is required.

## Debugging

If something doesn’t work as expected, enable debug logging in configuration.yaml:

  ```yaml
  logger:
    logs:
      homeassistant.components.hegel: debug
  ```
