# Example Sensor

This is a minimum implementation of an integration providing a sensor measurement.

### Installation

Add the following to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
sensor:
  - platform: switchbot_meter
    mac: 'aa:42:aa:42:aa:42'
    name: "Room1"
  - platform: switchbot_meter
    mac: 'bb:43:bb:43:bb:43'
    name: "Room2"
```
