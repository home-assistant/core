"""Constants for the SwitchBee Smart Home integration."""

from switchbee.device import DeviceType

DOMAIN = "switchbee"
SCAN_INTERVAL_SEC = 5
CONF_SCAN_INTERVAL = "scan_interval"
CONF_SWITCHES_AS_LIGHTS = "switch_as_light"
CONF_DEVICES = "devices"
CONF_DEFUALT_ALLOWED = [
    DeviceType.Switch.display,
    DeviceType.TimedPowerSwitch.display,
    DeviceType.TimedSwitch.display,
]
