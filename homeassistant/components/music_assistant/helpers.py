"""Helpers for the Music Assistant integration."""

from collections.abc import Callable, Coroutine
import functools
from typing import TYPE_CHECKING, Any

from music_assistant_models.errors import MusicAssistantError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

if TYPE_CHECKING:
    from music_assistant_client import MusicAssistantClient

    from . import MusicAssistantConfigEntry


def catch_musicassistant_error[**_P, _R](
    func: Callable[_P, Coroutine[Any, Any, _R]],
) -> Callable[_P, Coroutine[Any, Any, _R]]:
    """Check and convert commands to players."""

    @functools.wraps(func)
    async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        """Catch Music Assistant errors and convert to Home Assistant error."""
        try:
            return await func(*args, **kwargs)
        except MusicAssistantError as err:
            error_msg = str(err) or err.__class__.__name__
            raise HomeAssistantError(error_msg) from err

    return wrapper


@callback
def get_music_assistant_client(
    hass: HomeAssistant, config_entry_id: str
) -> MusicAssistantClient:
    """Get the Music Assistant client for the given config entry."""
    entry: MusicAssistantConfigEntry | None
    if not (entry := hass.config_entries.async_get_entry(config_entry_id)):
        raise ServiceValidationError("Entry not found")
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError("Entry not loaded")
    return entry.runtime_data.mass


async def async_resolve_mass_username(
    hass: HomeAssistant, user_id: str, available_usernames: list[str]
) -> str | None:
    """Resolve the Music Assistant username for the Home Assistant user."""
    if (user := await hass.auth.async_get_user(user_id)) is None:
        return None
    for cred in user.credentials:
        if cred.auth_provider_type == "homeassistant":
            username: str = cred.data["username"]
            break
    else:
        return None
    username = username.strip().lower()
    if username in available_usernames:
        return username
    return None
