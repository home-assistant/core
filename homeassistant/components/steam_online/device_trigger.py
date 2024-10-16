from __future__ import annotations

from collections.abc import Callable

import voluptuous as vol

from homeassistant.components.steam_online.const import CONF_ACCOUNT, DOMAIN
from homeassistant.components.steam_online.coordinator import SteamDataUpdateCoordinator
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

# Define the trigger types
TRIGGER_TYPES = {"friend_game_status_changed"}

TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for Steam devices."""
    triggers = []
    base_trigger = {
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
    }

    triggers += [
        {**base_trigger, CONF_TYPE: trigger_type} for trigger_type in TRIGGER_TYPES
    ]

    return triggers


@callback
def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: Callable,
    trigger_info: dict,
) -> callable:
    """Attach a trigger."""
    device_id = config[CONF_DEVICE_ID]

    # Get the config entry for the Steam account based on device_id
    config_entry = hass.config_entries.async_get_entry(
        list(dr.async_get(hass).async_get(device_id).config_entries)[0]
    )

    primary_user = config_entry.data[CONF_ACCOUNT]
    primary_user_entity_id = f"sensor.steam_{primary_user}"

    # Get Steam coordinator (to get friends' game data)
    coordinator: SteamDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def check_friend_game_status_change(variables: TemplateVarsType) -> bool:
        """Check if any friend has changed their game status."""

        # Fetch the current game for the primary user
        primary_game = hass.states.get(primary_user_entity_id).attributes.get("game_id")
        primary_state = hass.states.get(primary_user_entity_id).state

        # Check for each friend if they change their game status
        for friend_id, friend_data in coordinator.data.items():
            if friend_id != primary_user:
                friend_game = friend_data.get("game_id")
                friend_state = friend_data.get(
                    "state"
                )  # Assuming this attribute holds current state

                # Check if the friend's game state has changed
                if friend_game != primary_game or friend_state != "offline":
                    # Friend has changed their game status
                    return True
        return False

    if config[CONF_TYPE] == "friend_game_status_changed":
        trigger_method = check_friend_game_status_change

    # Attach trigger to Steam API update
    return coordinator.async_add_listener(
        lambda: action({} if trigger_method({}) else {})
    )
