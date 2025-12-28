"""Support for Bang & Olufsen diagnostics."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.event import DOMAIN as EVENT_DOMAIN
from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import BeoConfigEntry
from .const import DOMAIN
from .util import get_device_buttons, get_remote_keys, get_remotes


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: BeoConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    data: dict = {
        "config_entry": config_entry.as_dict(),
        "websocket_connected": config_entry.runtime_data.client.websocket_connected,
    }

    if TYPE_CHECKING:
        assert config_entry.unique_id

    entity_registry = er.async_get(hass)

    # Add media_player entity's state
    if entity_id := entity_registry.async_get_entity_id(
        MEDIA_PLAYER_DOMAIN, DOMAIN, config_entry.unique_id
    ):
        if state := hass.states.get(entity_id):
            state_dict = dict(state.as_dict())

            # Remove context as it is not relevant
            state_dict.pop("context")
            data["media_player"] = state_dict

    # Add button Event entity states (if enabled)
    for device_button in get_device_buttons(config_entry.data[CONF_MODEL]):
        if entity_id := entity_registry.async_get_entity_id(
            EVENT_DOMAIN, DOMAIN, f"{config_entry.unique_id}_{device_button}"
        ):
            if state := hass.states.get(entity_id):
                state_dict = dict(state.as_dict())

                # Remove context as it is not relevant
                state_dict.pop("context")
                data[f"{device_button}_event"] = state_dict

    # Get remotes
    for remote in await get_remotes(config_entry.runtime_data.client):
        # Get key Event entity states (if enabled)
        for key_type in get_remote_keys():
            if entity_id := entity_registry.async_get_entity_id(
                EVENT_DOMAIN,
                DOMAIN,
                f"{remote.serial_number}_{config_entry.unique_id}_{key_type}",
            ):
                if state := hass.states.get(entity_id):
                    state_dict = dict(state.as_dict())

                    # Remove context as it is not relevant
                    state_dict.pop("context")
                    data[f"remote_{remote.serial_number}_{key_type}_event"] = state_dict

        # Add remote Mozart model
        data[f"remote_{remote.serial_number}"] = dict(remote)

    return data
