# HA-MotionBlinds_BLE

This Home Assistant integration adds support for **MotionBlinds** bluetooth motors. Beware that this integration does not work for **Eve MotionBlinds** motors. **Eve MotionBlinds** can be added to Home Assistant using the [HomeKit](https://www.home-assistant.io/integrations/homekit_controller/) integration.


# Setup
MotionBlinds BLE devices will be automatically discovered by Home Assistant, and shown in the *Devices & Services* part of the Home Assistant settings. Additionally, there is the option to manually add a motor by entering the MAC code. This can be done by going to the integration and clicking on "*Setup another instance of MotionBlinds BLE*".

During the setup, you will be asked what kind of blind your MotionBlind is. There are 8 different blind types:

- **Roller blind**: has the ability to change position and speed.
- **Honeycomb blind**: has the ability to change position and speed.
- **Roman blind**: has the ability to change position and speed.
- **Venetian blind**: has the ability to change position, tilt and speed.
- **Venetian blind (tilt-only)**: has the ability to change tilt and speed.
- **Double Roller blind**: has the ability to change position, tilt and speed.
- **Curtain blind**: has the ability to change position. May need to be calibrated if the end positions are lost, which can be done by using the open/close cover button or the set cover position slider. This will trigger a calibration which will first make the curtain find the end positions after which it will run to the position as indicated by the command that was given.
- **Vertical blind**: has the ability to change position and tilt. May need to be calibrated if the end positions are lost, which has to be done using the MotionBlinds BLE app.

# Service

You can use the [homeassistant.update_entity](https://www.home-assistant.io/docs/scripts/service-calls/#homeassistant-services) service on a MotionBlinds BLE cover entity to connect to your MotionBlind and update the state of all entities belonging to the device. However, be aware that doing so may impact battery life.

# Troubleshooting

## Proxy

If you are using a proxy and are facing issues discovering your MotionBlinds, try unplugging your ESPHome proxy and plugging it back in.