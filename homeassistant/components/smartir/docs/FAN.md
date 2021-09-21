<p align="center">
  <a href="#"><img src="assets/smartir_fan.png" width="350" alt="SmartIR Media Player"></a>
</p>

For this platform to work, we need a .json file containing all the necessary IR or RF commands.
Find your device's brand code [here](FAN.md#available-codes-for-fan-devices) and add the number in the `device_code` field. The compoenent will download it to the correct folder. If your device is not working, you will need to learn your own codes and place the .json file in `smartir/codes/fan/` subfolders. Please note that the `device_code` field only accepts positive numbers. The .json extension is not required.

## Configuration variables:
**name** (Optional): The name of the device<br />
**unique_id** (Optional): An ID that uniquely identifies this device. If two devices have the same unique ID, Home Assistant will raise an exception.<br />
**device_code** (Required): ...... (Accepts only positive numbers)<br />
**controller_data** (Required): The data required for the controller to function. Enter the IP address of the Broadlink device **(must be an already configured device)**, or the entity id of the Xiaomi IR controller, or the MQTT topic on which to send commands.<br />
**power_sensor** (Optional): *entity_id* for a sensor that monitors whether your device is actually On or Off. This may be a power monitor sensor. (Accepts only on/off states)<br />

## Example (using broadlink controller):
Add a Broadlink RM device named "Bedroom" via config flow (read the [docs](https://www.home-assistant.io/integrations/broadlink/)).

```yaml
smartir:

fan:
  - platform: smartir
    name: Bedroom fan
    unique_id: bedroom_fan
    device_code: 1000
    controller_data: remote.bedroom_remote
    power_sensor: binary_sensor.fan_power
```
## Example (using xiaomi controller):
```yaml
smartir:

remote:
  - platform: xiaomi_miio
    host: 192.168.10.10
    token: YOUR_TOKEN

fan:
  - platform: smartir
    name: Bedroom fan
    unique_id: bedroom_fan
    device_code: 2000
    controller_data: remote.xiaomi_miio_192_168_10_10
    power_sensor: binary_sensor.fan_power
```

## Example (using mqtt controller):
```yaml
smartir:

fan:
  - platform: smartir
    name: Bedroom fan
    unique_id: bedroom_fan
    device_code: 3000
    controller_data: home-assistant/bedroom-fan/command
    power_sensor: binary_sensor.fan_power
```

## Example (using LOOKin controller):
```yaml
smartir:

fan:
  - platform: smartir
    name: Bedroom fan
    unique_id: bedroom_fan
    device_code: 4000
    controller_data: 192.168.10.10
    power_sensor: binary_sensor.fan_power
```

## Example (using ESPHome):
ESPHome configuration example:
```yaml
esphome:
  name: my_espir
  platform: ESP8266
  board: esp01_1m

api:
  services:
    - service: send_raw_command
      variables:
        command: int[]
      then:
        - remote_transmitter.transmit_raw:
            code: !lambda 'return command;'

remote_transmitter:
  pin: GPIO14
  carrier_duty_percent: 50%
```
HA configuration.yaml:
```yaml
smartir:

fan:
  - platform: smartir
    name: Bedroom fan
    unique_id: bedroom_fan
    device_code: 4000
    controller_data: my_espir_send_raw_command
    power_sensor: binary_sensor.fan_power
```

## Available codes for Fan devices:
The following are the code files created by the amazing people in the community. Before you start creating your own code file, try if one of them works for your device. **Please open an issue if your device is working and not included in the supported models.**
Contributing to your own code files is welcome. However, we do not accept incomplete files as well as files related to MQTT controllers.

#### Kaze
| Code | Supported Models | Controller |
| ------------- | -------------------------- | ------------- |
[1000](../codes/fan/1000.json)|Unknown|Broadlink

#### Acorn
| Code | Supported Models | Controller |
| ------------- | -------------------------- | ------------- |
[1020](../codes/fan/1020.json)|Unknown|Broadlink

#### Lucci Air
| Code | Supported Models | Controller |
| ------------- | -------------------------- | ------------- |
[1040](../codes/fan/1040.json)|Aria|Broadlink

#### Super Fan
| Code | Supported Models | Controller |
| ------------- | -------------------------- | ------------- |
[1060](../codes/fan/1060.json)|A1|Broadlink

#### Hampton Bay
| Code | Supported Models | Controller |
| ------------- | -------------------------- | ------------- |
[1080](../codes/fan/1080.json)|Unknown|Broadlink

#### Pacific
| Code | Supported Models | Controller |
| ------------- | -------------------------- | ------------- |
[1100](../codes/fan/1100.json)|Unknown|Broadlink

#### Europace
| Code | Supported Models | Controller |
| ------------- | -------------------------- | ------------- |
[1120](../codes/fan/1120.json)|Unknown|Broadlink
