---
title: Vitrea
description: Instructions on how to integrate Vitrea devices within Home Assistant.
ha_category:
  - Switch
  - Sensor
  - Number
ha_release: 2025.2
ha_iot_class: Local Polling
ha_config_flow: true
ha_codeowners:
  - "@solangek"
ha_domain: vitrea
ha_platforms:
  - sensor
  - switch
  - number
---

The Vitrea integration allows you to control and monitor Vitrea heating system devices within Home Assistant.

## Supported devices

This integration supports Vitrea controllers and their associated components including:

- Blinds sensors
- Switch controls
- Timer controls for scheduling boilers switches

## Configuration

{% include integrations/config_flow.md %}

The integration will discover your Vitrea device on the local network and prompt you to configure it.

### Manual configuration

If automatic discovery doesn't work, you can manually configure the integration by providing:

- **Host**: The IP address of your Vitrea controller
- **Port**: The port number (default: 11502)

## Entities

The Vitrea integration creates several types of entities depending on your device configuration:

### Switches

- Standard on/off switches
- Timer-enabled switches with configurable duration (0-120 minutes)

### Covers (Blinds)

- Open, close, and stop controls
- Position control (0-100%)
- Current position feedback
-

### Number Entities (Timers)

- Timer controls for switches that support timed operation
- Range: 0-120 minutes
- Used to set default timer duration for associated switches

### Service `vitrea.set_timer`

Set a timer for a specific switch entity (boiler).

| Service data attribute | Optional | Description                            |
| ---------------------- | -------- | -------------------------------------- |
| `entity_id`            | no       | The switch entity to set the timer for |
| `minutes`              | no       | Timer duration in minutes (0-120)      |

Example service call:

```yaml
service: vitrea.set_timer
target:
  entity_id: switch.vitrea_zone_1
data:
  minutes: 30
```

## Device Management

All Vitrea devices are automatically grouped under their respective hub device in the device registry. The integration supports:

- **Automatic device discovery**: New devices are detected automatically
- **Real-time updates**: Device states are updated in real-time via the Vitrea hub
- **Assumed state**: Entities use assumed state for reliable operation

## Troubleshooting

### Connection Issues

- Ensure your Vitrea hub is powered on and connected to the network
- Verify the IP address and port are correct. The Vitrea hub typically provides 3 consecutive ports, one is used by the Vitrea admin app, the second is used by the integration and the third is used by the Vitrea app.
- Check that no firewall is blocking communication on the specified port

### Device Not Appearing

- Wait a few moments for automatic discovery to complete
- Restart the Vitrea hub if devices are not detected
- Check the Vitrea hub's device configuration

### Timer Functions Not Working

- Ensure the switch supports timer functionality
- Verify the timer range is within 0-120 minutes
- Check that the associated timer number entity is properly configured
