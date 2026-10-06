"""Constants for the Homeassistant integration."""

from typing import TYPE_CHECKING, Final

from homeassistant import core as ha
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .exposed_entities import ExposedEntities

DOMAIN = ha.DOMAIN

DATA_EXPOSED_ENTITIES: HassKey[ExposedEntities] = HassKey(f"{DOMAIN}.exposed_entities")
DATA_STOP_HANDLER = f"{DOMAIN}.stop_handler"

SERVICE_HOMEASSISTANT_STOP: Final = "stop"
SERVICE_HOMEASSISTANT_RESTART: Final = "restart"
SERVICE_CHECK_CONFIG: Final = "check_config"
SERVICE_RELOAD_ALL: Final = "reload_all"
SERVICE_RELOAD_CONFIG_ENTRY: Final = "reload_config_entry"
SERVICE_RELOAD_CORE_CONFIG: Final = "reload_core_config"
SERVICE_RELOAD_CUSTOM_TEMPLATES: Final = "reload_custom_templates"
SERVICE_SET_LOCATION: Final = "set_location"
SERVICE_UPDATE_ENTITY: Final = "update_entity"

SHUTDOWN_SERVICES: Final = (
    SERVICE_HOMEASSISTANT_STOP,
    SERVICE_HOMEASSISTANT_RESTART,
)

ATTR_ENTRY_ID: Final = "entry_id"
ATTR_SAFE_MODE: Final = "safe_mode"
