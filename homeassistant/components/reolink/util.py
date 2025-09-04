"""Utility functions for the Reolink component."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from reolink_aio.exceptions import (
    ApiError,
    CredentialsInvalidError,
    InvalidContentTypeError,
    InvalidParameterError,
    LoginError,
    NoDataError,
    NotSupportedError,
    ReolinkConnectionError,
    ReolinkError,
    ReolinkTimeoutError,
    SubscriptionError,
    UnexpectedDataError,
)

from homeassistant import config_entries
from homeassistant.components.media_source import Unresolvable
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import Store
from homeassistant.helpers.translation import async_get_exception_message
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

if TYPE_CHECKING:
    from .host import ReolinkHost

STORAGE_VERSION = 1

type ReolinkConfigEntry = config_entries.ConfigEntry[ReolinkData]


@dataclass
class ReolinkData:
    """Data for the Reolink integration."""

    host: ReolinkHost
    device_coordinator: DataUpdateCoordinator[None]
    firmware_coordinator: DataUpdateCoordinator[None]


def is_connected(hass: HomeAssistant, config_entry: config_entries.ConfigEntry) -> bool:
    """Check if an existing entry has a proper connection."""
    return (
        hasattr(config_entry, "runtime_data")
        and config_entry.state == config_entries.ConfigEntryState.LOADED
        and config_entry.runtime_data.device_coordinator.last_update_success
    )


def get_host(hass: HomeAssistant, config_entry_id: str) -> ReolinkHost:
    """Return the Reolink host from the config entry id."""
    config_entry: ReolinkConfigEntry | None = hass.config_entries.async_get_entry(
        config_entry_id
    )
    if config_entry is None:
        raise Unresolvable(
            f"Could not find Reolink config entry id '{config_entry_id}'."
        )
    return config_entry.runtime_data.host


def get_store(hass: HomeAssistant, config_entry_id: str) -> Store[str]:
    """Return the reolink store."""
    return Store[str](hass, STORAGE_VERSION, f"{DOMAIN}.{config_entry_id}.json")


def get_device_uid_and_ch(
    device: dr.DeviceEntry | tuple[str, str], host: ReolinkHost
) -> tuple[list[str], int | None, bool]:
    """Get the channel and the split device_uid from a reolink DeviceEntry."""
    device_uid = []
    is_chime = False

    if isinstance(device, dr.DeviceEntry):
        dev_ids = device.identifiers
    else:
        dev_ids = {device}

    for dev_id in dev_ids:
        if dev_id[0] == DOMAIN:
            device_uid = dev_id[1].split("_")
            if device_uid[0] == host.unique_id:
                break

    if len(device_uid) < 2:
        # NVR itself
        ch = None
    elif device_uid[1].startswith("ch") and len(device_uid[1]) <= 5:
        ch = int(device_uid[1][2:])
    elif device_uid[1].startswith("chime"):
        ch = int(device_uid[1][5:])
        is_chime = True
    else:
        device_uid_part = "_".join(device_uid[1:])
        ch = host.api.channel_for_uid(device_uid_part)
    return (device_uid, ch, is_chime)


def check_translation_key(err: ReolinkError) -> str | None:
    """Check if the translation key from the upstream library is present."""
    if not err.translation_key:
        return None
    if async_get_exception_message(DOMAIN, err.translation_key) == err.translation_key:
        # translation key not found in strings.json
        return None
    return err.translation_key


_EXCEPTION_TO_TRANSLATION_KEY = {
    ApiError: "api_error",
    InvalidContentTypeError: "invalid_content_type",
    CredentialsInvalidError: "invalid_credentials",
    LoginError: "login_error",
    NoDataError: "no_data",
    UnexpectedDataError: "unexpected_data",
    NotSupportedError: "not_supported",
    SubscriptionError: "subscription_error",
    ReolinkConnectionError: "connection_error",
    ReolinkTimeoutError: "timeout",
}


# Decorators
def raise_translated_error[**P, R](
    func: Callable[P, Awaitable[R]],
) -> Callable[P, Coroutine[Any, Any, R]]:
    """Wrap a reolink-aio function to translate any potential errors."""

    async def decorator_raise_translated_error(*args: P.args, **kwargs: P.kwargs) -> R:
        """Try a reolink-aio function and translate any potential errors."""
        try:
            return await func(*args, **kwargs)
        except InvalidParameterError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=check_translation_key(err) or "invalid_parameter",
                translation_placeholders={"err": str(err)},
            ) from err
        except ReolinkError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=check_translation_key(err)
                or _EXCEPTION_TO_TRANSLATION_KEY.get(type(err), "unexpected"),
                translation_placeholders={"err": str(err)},
            ) from err

    return decorator_raise_translated_error
