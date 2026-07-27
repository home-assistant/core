"""Utils for Mikrotik."""

from collections.abc import Generator
from contextlib import contextmanager

from librouteros.exceptions import ConnectionClosed, LibRouterosError

from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)

from .const import DOMAIN
from .errors import CannotConnect, LoginError


@contextmanager
def mikrotik_config_entry_errors(suppress_errors: bool = False) -> Generator[None]:
    """Handle common Mikrotik API exceptions as ConfigEntry errors."""
    try:
        yield
    except LoginError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err
    except (CannotConnect, OSError, TimeoutError, ConnectionClosed) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": repr(err)},
        ) from err
    except LibRouterosError as err:
        if not suppress_errors:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="mikrotik_api_error",
                translation_placeholders={"error": repr(err)},
            ) from err

        if "no such command prefix" not in str(err):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="mikrotik_api_error",
                translation_placeholders={"error": repr(err)},
            ) from err
