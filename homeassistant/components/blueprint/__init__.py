"""The blueprint integration."""
from . import websocket_api
from .const import DOMAIN  # noqa
from .errors import (  # noqa
    BlueprintException,
    BlueprintWithNameException,
    FailedToLoad,
    InvalidBlueprint,
    InvalidBlueprintInputs,
    MissingPlaceholder,
)
from .models import Blueprint, BlueprintInputs, DomainBlueprints  # noqa
from .schemas import is_blueprint_instance_config  # noqa


async def async_setup(hass, config):
    """Set up the blueprint integration."""
    websocket_api.async_setup(hass)
    return True
