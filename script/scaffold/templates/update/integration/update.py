"""Update support for the NEW_NAME integration."""
from typing import Any

from homeassistant.components.update import IntegrationUpdateFailed, UpdateDescription
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_list_updates(hass: HomeAssistant) -> list[UpdateDescription]:
    """List all updates available."""
    updates: list[UpdateDescription] = []
    # TODO List all updates available.
    # my_api = # hass.data[DOMAIN]
    # for entry in my_api.data:
    #     if entry.update_available:
    #        updates.append(UpdateDescription(...))

    return updates


async def async_perform_update(
    hass: HomeAssistant,
    identifier: str,
    version: str,
    **kwargs: Any,
) -> None:
    """Perform an update."""
    # TODO Perform an update based on identifier and version.
    # The identifier and version is provided by the update description created in async_list_updates
    # raise IntegrationUpdateFailed if the update failed.
