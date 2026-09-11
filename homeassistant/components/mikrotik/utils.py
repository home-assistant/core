"""Utils for Mikrotik."""

from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timedelta

from librouteros.exceptions import ConnectionClosed, LibRouterosError

from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util.dt import utcnow

from .const import DOMAIN, LOGGER
from .errors import CannotConnect, LoginError


def percentage(total: float, free: float) -> float | None:
    """Return the used percentage for a total/free pair, or None if total is zero."""
    if total == 0:
        return None
    return (total - free) / total * 100


def calculate_uptime(uptime_string: str) -> datetime | None:
    """Calculate uptime from a RouterOS duration string, e.g. "1d3h39m30s"."""
    total = 0
    num = 0

    for ch in uptime_string.strip():
        if ch.isdigit():
            num = num * 10 + int(ch)
        else:
            if ch == "w":
                total += num * (60 * 60 * 24 * 7)
            elif ch == "d":
                total += num * (60 * 60 * 24)
            elif ch == "h":
                total += num * (60 * 60)
            elif ch == "m":
                total += num * 60
            elif ch == "s":
                total += num
            else:
                LOGGER.warning("Unknown uptime format: %s", uptime_string)
                return None

            num = 0

    if num != 0:
        LOGGER.warning("Unknown uptime format: %s", uptime_string)
        return None

    return utcnow() - timedelta(seconds=total)


@contextmanager
def mikrotik_config_entry_errors(
    suppress_errors: bool = False, during_setup: bool = False
) -> Generator[None]:
    """Handle common Mikrotik API exceptions as ConfigEntry errors.

    `during_setup`:
      - True when called from `async_setup_entry` so connectivity errors raise
        `ConfigEntryNotReady`.
      - False when called from the coordinator's update cycle, so connectivity errors
        raise `UpdateFailed` instead.
    """
    try:
        yield
    except LoginError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err
    except (CannotConnect, OSError, TimeoutError, ConnectionClosed) as err:
        if during_setup:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": repr(err)},
            ) from err
        raise UpdateFailed(
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
