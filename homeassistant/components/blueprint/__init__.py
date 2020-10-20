"""The blueprint integration."""
from typing import Any

from homeassistant.core import callback

from . import websocket_api
from .const import CONF_BLUEPRINT, DOMAIN  # noqa
from .errors import (  # noqa
    BlueprintException,
    BlueprintWithNameException,
    FailedToLoad,
    InvalidBlueprint,
    InvalidBlueprintInputs,
    MissingPlaceholder,
)
from .models import Blueprint, BlueprintInputs, DomainBlueprints  # noqa


@callback
def is_blueprint_config(config: Any) -> bool:
    """Return if it is a blueprint config."""
    return isinstance(config, dict) and CONF_BLUEPRINT in config


async def async_setup(hass, config):
    """Set up the blueprint integration."""
    websocket_api.async_setup(hass)
    return True
