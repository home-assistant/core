"""Helpers for the Music Assistant integration."""

from collections.abc import Callable, Coroutine
import functools
from typing import TYPE_CHECKING, Any

from music_assistant_models.auth import UserRole
from music_assistant_models.errors import MusicAssistantError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import DOMAIN

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


async def async_get_available_mass_usernames(mass: MusicAssistantClient) -> list[str]:
    """Get available Music Assistant usernames which can be used in Home Assistant."""
    users = await mass.auth.list_users()
    return [
        user.username for user in users if user.enabled and user.role != UserRole.GUEST
    ]


async def async_resolve_mass_username(
    hass: HomeAssistant, mass: MusicAssistantClient, user_id: str
) -> str | None:
    """Resolve the Music Assistant username for the Home Assistant user."""
    available_usernames = await async_get_available_mass_usernames(mass)
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


async def async_verify_mass_username_availability(
    mass: MusicAssistantClient, username: str, raise_on_error: bool = False
) -> bool:
    """Verify Music Assistant username availability for service calls."""
    available_usernames = await async_get_available_mass_usernames(mass)
    if username not in available_usernames and raise_on_error:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_username",
            translation_placeholders={
                "username": username,
                "available_usernames": ", ".join(available_usernames),
            },
        )
    return username in available_usernames
