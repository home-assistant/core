"""Constants for the Qbus integration."""

from homeassistant.const import Platform

DOMAIN = "qbus"
PLATFORMS: list[str] = [Platform.SWITCH]

CONF_CONFIG_TOPIC = "cloudapp/QBUSMQTTGW/getConfig"
CONFIG_TOPIC = "cloudapp/QBUSMQTTGW/config/#"

NAME = "name"
CONF_SERIAL = "serial"
CONF_STATE_MESSAGE = "state_message"
DEVICE_CONFIG_TOPIC = "conf_topic"
