"""The blueprint integration."""
from . import websocket_api
from .const import DOMAIN  # noqa: F401
from .errors import (  # noqa: F401
    BlueprintException,
    BlueprintWithNameException,
    FailedToLoad,
    InvalidBlueprint,
    InvalidBlueprintInputs,
    MissingInput,
)
from .models import Blueprint, BlueprintInputs, DomainBlueprints  # noqa: F401
from .schemas import is_blueprint_instance_config  # noqa: F401


async def async_setup(hass, config):
    """Set up the blueprint integration."""
    websocket_api.async_setup(hass)
    return True
