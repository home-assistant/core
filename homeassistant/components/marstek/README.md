# Home Assistant  Integration for Marstek 

[English](../README.md) | [简体中文](./README_zh.md)

Marstek Integration is an integration component provided by Marstek official for Home Assistant, which can be used to monitor and control Marstek devices.

## Requirements

> Home Assistant version requirement:
>
> - Core ：^2025.10.0
> - HAOS ：^15.0
>
> Marstek devices and Home Assistant need to be on the same local network
>
> Marstek devices need to have the OPEN API enabled

## Installation

### Method 1: Git clone from GitHub

```bash
cd config
git clone https://github.com/MarstekEnergy/ha_marstek.git
```

### Method 2: Manually installation via Samba / SSH

Download the Marstek integration file and copy the `custom_components/Marstek` folder to the `config/custom_components/` directory in Home Assistant.

## Communication Protocol

### UDP 
- Default port ：30000
- Timeout ：10秒
- Communication mode ：
  - OPEN API
  - Bidirectional UDP communication

- ES.SetMode retry mechanism：
  - Priority principle: All polling requests will be stopped when the ES.SetMode directive is issued
  - Add index avoidance


### Main Command Set

In the current version, the device supports the following main commands (provided by OPEN API):

- Device Discovery: `Marstek.GetDevice`
- Battery Status: `Bat.GetStatus`
- Energy Storage Status: `ES.GetStatus`
- Mode Setting: `ES.SetMode`
- PV Status (available on some devices): `PV.GetStatus`


## Configuration Guide

1. Add integration through Home Assistant UI
2. The integration will automatically search for Marstek devices on the local network: typically shows "[Device Name] [Firmware Version] ([Wi-Fi Name]) - [Device IP]"
3. Select the device to add and confirm, UDP polling for device status will be automatically enabled
4. Add automation: currently provides three modes to control device charging/discharging - charge, discharge, and stop

## Data Update Mechanism

- Uses local push mechanism (UDP polling) to receive device status updates
- Real-time response to device state changes
- Maintains continuous connection with the device

## Error Handling

The integration implements the following error handling mechanisms:

- Automatic reconnection for network interruptions
- Device response timeout handling
- Configuration error notifications

## Important Notes

1. Ensure that the OPEN API is enabled on the device
2. Ensure the device and Home Assistant are on the same network segment
3. UDP port 30000 must remain open
4. Wait for the device discovery process to complete during initial configuration

## Technical Support

For technical issues, please seek support through:

- Discuss on the [Home Assistant Community](https://community.home-assistant.io/)
- Submit a GitHub Issue
- Contact device manufacturer's technical support

## Change log

### v0.1.0
- Initial version release
- Device auto-discovery
- Support for basic device status monitoring and charge/discharge control commands

## FAQ

1. Which devices are supported?

   Supports Venus A, Venus D, Venus E 3.0 with the latest firmware version, and other Marstek devices that support OPEN API communication.

2. Why can't I find my device?

   - OPEN API is not enabled
   - Ensure Marstek devices and Home Assistant are on the same network segment and port 30000 is open
   - The integration searches for devices via UDP broadcast, network fluctuations may affect device-HA communication, try again if needed

3. What is OPEN API?

   OPEN API is a communication interface provided by Marstek device firmware for querying device status and controlling certain functions in a local network environment. **Note: OPEN API is not enabled by default, it requires official MQTT protocol to be enabled.** Alternatively, future versions of the Marstek APP will provide an option to enable it.
