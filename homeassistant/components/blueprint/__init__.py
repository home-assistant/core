"""The blueprint integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import websocket_api
from .const import CONF_USE_BLUEPRINT, DOMAIN
from .errors import BlueprintException, BlueprintInUse
from .models import Blueprint, BlueprintInputs, DomainBlueprints
from .schemas import BLUEPRINT_SCHEMA, is_blueprint_instance_config

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

__all__ = [
    "BLUEPRINT_SCHEMA",
    "CONF_USE_BLUEPRINT",
    "DOMAIN",
    "Blueprint",
    "BlueprintException",
    "BlueprintInUse",
    "BlueprintInputs",
    "DomainBlueprints",
    "is_blueprint_instance_config",
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the blueprint integration."""
    websocket_api.async_setup(hass)
    return True
