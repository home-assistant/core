"""Constants for the Homeassistant integration."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant import core as ha
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .exposed_entities import ExposedEntities

DOMAIN = ha.DOMAIN

DATA_EXPOSED_ENTITIES: HassKey[ExposedEntities] = HassKey(f"{DOMAIN}.exposed_entities")
DATA_STOP_HANDLER = f"{DOMAIN}.stop_handler"


class HomeAssistantService(StrEnum):
    """Store keys for Home Assistant services."""

    CHECK_CONFIG = "check_config"
    RELOAD_ALL = "reload_all"
    RELOAD_CONFIG_ENTRY = "reload_config_entry"
    RELOAD_CORE_CONFIG = "reload_core_config"
    RELOAD_CUSTOM_TEMPLATES = "reload_custom_templates"
    RESTART = "restart"
    SAVE_PERSISTENT_STATES = "save_persistent_states"
    SET_LOCATION = "set_location"
    STOP = "stop"
    TOGGLE = "toggle"
    TURN_OFF = "turn_off"
    TURN_ON = "turn_on"
    UPDATE_ENTITY = "update_entity"


# To be deprecated at a later stage, replaced by HomeAssistantService
SERVICE_HOMEASSISTANT_STOP: Final = HomeAssistantService.STOP.value
SERVICE_HOMEASSISTANT_RESTART: Final = HomeAssistantService.RESTART.value
