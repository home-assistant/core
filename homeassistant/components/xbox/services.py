"""Services for the Xbox integration."""

from __future__ import annotations

from typing import Any, cast

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import JsonValueType
from homeassistant.util.dt import UTC

from .const import DOMAIN
from .coordinator import XboxConfigEntry

ATTR_CONFIG_ENTRY_ID = "config_entry_id"

SERVICE_GET_RECENTLY_PLAYED_GAMES = "get_recently_played_games"
SERVICE_GET_RECENTLY_PLAYED_GAMES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
    }
)


def _async_get_entry(hass: HomeAssistant, config_entry_id: str) -> XboxConfigEntry:
    """Get the Xbox config entry."""
    if not (entry := hass.config_entries.async_get_entry(config_entry_id)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="integration_not_found",
            translation_placeholders={"target": DOMAIN},
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_loaded",
            translation_placeholders={"target": entry.title},
        )
    return cast(XboxConfigEntry, entry)


async def _async_get_recently_played_games(
    call: ServiceCall,
) -> ServiceResponse:
    """Get recently played games from Xbox.

    Returns a dictionary containing:
    - xuid: The Xbox User ID of the account
    - account_name: The display name of the Xbox account
    - games: List of recently played games with details

    Example template sensor using this service data:

    Create sensors that track your Xbox gaming activity using the service
    response data. Each sensor can access account info (xuid, account_name)
    and game details (title, last_played, achievements, gamerscore, images).
    Configure template sensors with trigger-based updates to call the service
    periodically and extract specific metrics from the returned game list.
    """
    entry = _async_get_entry(call.hass, call.data[ATTR_CONFIG_ENTRY_ID])
    coordinator = entry.runtime_data.title_history

    if coordinator.data is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="no_data_available",
        )

    title_history = coordinator.data
    games_list: list[dict[str, Any]] = []

    if title_history.titles:
        for game in title_history.titles:
            game_data: dict[str, Any] = {
                "title": game.name or "Unknown",
                "title_id": game.title_id or "",
            }

            if game.title_history:
                game_data["last_played"] = (
                    game.title_history.last_time_played.replace(tzinfo=UTC).isoformat()
                    if game.title_history.last_time_played
                    else None
                )

            if game.achievement:
                game_data.update(
                    {
                        "achievements_earned": game.achievement.current_achievements,
                        "achievements_total": game.achievement.total_achievements,
                        "gamerscore_earned": game.achievement.current_gamerscore,
                        "gamerscore_total": game.achievement.total_gamerscore,
                        "achievement_progress": int(
                            game.achievement.progress_percentage
                        ),
                    }
                )

            # Add image URL if available
            if game.images:
                image_url = next(
                    (i.url for i in game.images if i.type == "Poster"), None
                ) or next((i.url for i in game.images if i.type == "Logo"), None)
                if image_url:
                    game_data["image_url"] = image_url

            games_list.append(game_data)

    return {
        "xuid": coordinator.xuid,
        "account_name": entry.title,
        "games": cast(list[JsonValueType], games_list),
    }


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Xbox integration."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_RECENTLY_PLAYED_GAMES,
        _async_get_recently_played_games,
        schema=SERVICE_GET_RECENTLY_PLAYED_GAMES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
