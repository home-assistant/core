"""Constants for the Kitchen Sink integration."""

from collections.abc import Callable

from homeassistant.util.hass_dict import HassKey

DOMAIN = "kitchen_sink"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_INFRARED_RECEIVER_ENTITY_ID = "infrared_receiver_entity_id"
DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)

INFRARED_FAN_ADDRESS = 0x1234
INFRARED_CMD_POWER_ON = 0x01
INFRARED_CMD_POWER_OFF = 0x02
INFRARED_CMD_SPEED_LOW = 0x03
INFRARED_CMD_SPEED_MEDIUM = 0x04
INFRARED_CMD_SPEED_HIGH = 0x05
