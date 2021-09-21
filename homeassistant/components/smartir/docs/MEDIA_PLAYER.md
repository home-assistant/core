<p align="center">
  <a href="#"><img src="assets/smartir_mediaplayer.png" width="350" alt="SmartIR Media Player"></a>
</p>

For this platform to work, we need a .json file containing all the necessary IR commands.
Find your device's brand code [here](MEDIA_PLAYER.md#available-codes-for-tv-devices) and add the number in the `device_code` field. The compoenent will download it to the correct folder. If your device is not working, you will need to learn your own codes and place the .json file in `smartir/codes/media_player/` subfolders. Please note that the `device_code` field only accepts positive numbers. The .json extension is not required.

## Configuration variables:
**name** (Optional): The name of the device<br />
**unique_id** (Optional): An ID that uniquely identifies this device. If two devices have the same unique ID, Home Assistant will raise an exception.<br />
**device_code** (Required): ...... (Accepts only positive numbers)<br />
**controller_data** (Required): The data required for the controller to function. Enter the IP address of the Broadlink device **(must be an already configured device)**, or the entity id of the Xiaomi IR controller, or the MQTT topic on which to send commands.<br />
**power_sensor** (Optional): *entity_id* for a sensor that monitors whether your device is actually On or Off. This may be a power monitor sensor. (Accepts only on/off states)<br />
**source_names** (Optional): Override the names of sources as displayed in HomeAssistant (see below)<br />

## Example (using broadlink controller):
Add a Broadlink RM device named "Bedroom" via config flow (read the [docs](https://www.home-assistant.io/integrations/broadlink/)).

```yaml
smartir:

media_player:
  - platform: smartir
    name: Living room TV
    unique_id: living_room_tv
    device_code: 1000
    controller_data: remote.bedroom_remote
    power_sensor: binary_sensor.tv_power
```

## Example (using xiaomi controller):
```yaml
smartir:

remote:
  - platform: xiaomi_miio
    host: 192.168.10.10
    token: YOUR_TOKEN
    
media_player:
  - platform: smartir
    name: Living room TV
    unique_id: living_room_tv
    device_code: 2000
    controller_data: remote.xiaomi_miio_192_168_10_10
    power_sensor: binary_sensor.tv_power
```

## Example (using mqtt controller):
```yaml
smartir:

media_player:
  - platform: smartir
    name: Living room TV
    unique_id: living_room_tv
    device_code: 3000
    controller_data: home-assistant/living-room-tv/command
    power_sensor: binary_sensor.tv_power
```

## Example (using LOOKin controller):
```yaml
smartir:

media_player:
  - platform: smartir
    name: Living room TV
    unique_id: living_room_tv
    device_code: 4000
    controller_data: 192.168.10.10
    power_sensor: binary_sensor.tv_power
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

media_player:
  - platform: smartir
    name: Living room TV
    unique_id: living_room_tv
    device_code: 2000
    controller_data: my_espir_send_raw_command
    power_sensor: binary_sensor.tv_power
```

### Overriding Source Names
Source names in device files are usually set to the name that the media player uses. These often aren't very descriptive, so you can override these names in the configuration file. You can also remove a source by setting its name to `null`.

```yaml
media_player:
  - platform: smartir
    name: Living room TV
    unique_id: living_room_tv
    device_code: 1000
    controller_data: 192.168.10.10
    source_names:
      HDMI1: DVD Player
      HDMI2: Xbox
      VGA: null
```

## Available codes for TV devices:
The following are the code files created by the amazing people in the community. Before you start creating your own code file, try if one of them works for your device. **Please open an issue if your device is working and not included in the supported models.**
Contributing to your own code files is welcome. However, we do not accept incomplete files as well as files related to MQTT controllers.

#### Philips
| Code | Supported Models | Controller |
| ------------- | -------------------------- | ------------- |
[1000](../codes/media_player/1000.json)|26PFL560H|Broadlink

#### Sony
| Code | Supported Models | Controller |
| ------------- | -------------------------- | ------------- |
[1020](../codes/media_player/1020.json)|KDL-46HX800|Broadlink

#### LG
| Code | Supported Models | Controller |
| ------------- | -------------------------- | ------------- |
[1040](../codes/media_player/1040.json)|22MT47DC|Broadlink
[1041](../codes/media_player/1041.json)|LH6235D|Broadlink

#### Samsung
| Code | Supported Models | Controller |
| ------------- | -------------------------- | ------------- |
[1060](../codes/media_player/1060.json)|UE40F6500<br>LE40D550<br>UE40H6400<br>UE40H7000SL|Broadlink
[1061](../codes/media_player/1061.json)|UE40C6000<br>UE40D6500<br>UE32H5500<br>UE22D5000|Broadlink

#### Insignia
| Code | Supported Models | Controller |
| ------------- | -------------------------- | ------------- |
[1080](../codes/media_player/1080.json)|NS-42D510NA15|Broadlink

#### Toshiba
| Code | Supported Models | Controller |
| ------------- | -------------------------- | ------------- |
[1100](../codes/media_player/1100.json)|42C3530D|Broadlink

#### Yamaha
| Code | Supported Models | Controller |
| ------------- | -------------------------- | ------------- |
[1120](../codes/media_player/1120.json)|Unknown|Broadlink
[1121](../codes/media_player/1121.json)|Yamaha RX-V375 and others (RAV463/ZA113500 remote)|Broadlink
[1122](../codes/media_player/1122.json)|VR50590 remote|Broadlink

#### RME
| Code | Supported Models | Controller |
| ------------- | -------------------------- | ------------- |
[1140](../codes/media_player/1140.json)|ADI-2 DAC FS|Broadlink

#### Logitech
| Code | Supported Models | Controller |
| ------------- | -------------------------- | ------------- |
[1160](../codes/media_player/1160.json)|Z906|Broadlink
[1161](../codes/media_player/1161.json)|Z-5500|Broadlink

#### TCL
| Code | Supported Models | Controller |
| ------------- | -------------------------- | ------------- |
[1180](../codes/media_player/1180.json)|55EP640|Broadlink

#### Pace
| Code | Supported Models | Controller |
| ------------- | -------------------------- | ------------- |
[1200](../codes/media_player/1200.json)|TDS850NNZ <br> TDC850NF|Broadlink

#### Silver
| Code | Supported Models | Controller |
| ------------- | -------------------------- | ------------- |
[1220](../codes/media_player/1220.json)|MEO|Broadlink

#### TurboX
| Code | Supported Models | Controller |
| ------------- | -------------------------- | ------------- |
[1240](../codes/media_player/1240.json)|TXV-2420|Broadlink
