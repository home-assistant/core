"""Helpers for the Music Assistant integration."""

from collections.abc import Callable, Coroutine, Generator
from contextlib import contextmanager
import functools
from typing import TYPE_CHECKING, Any

from music_assistant_models.errors import MusicAssistantError, UserNotFoundError

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


@contextmanager
def catch_user_not_found(username: str | None) -> Generator[None]:
    """Convert a server UserNotFoundError into a translated invalid_username error."""
    if username is None:
        yield
        return
    try:
        yield
    except UserNotFoundError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_username",
            translation_placeholders={"username": username},
        ) from err


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
