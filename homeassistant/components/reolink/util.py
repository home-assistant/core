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
    device: dr.DeviceEntry, host: ReolinkHost
) -> tuple[list[str], int | None, bool]:
    """Get the channel and the split device_uid from a reolink DeviceEntry."""
    device_uid = [
        dev_id[1].split("_") for dev_id in device.identifiers if dev_id[0] == DOMAIN
    ][0]

    is_chime = False
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
            key = err.translation_key if err.translation_key else "invalid_parameter"
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=key,
                translation_placeholders={"err": str(err)},
            ) from err
        except ApiError as err:
            key = err.translation_key if err.translation_key else "api_error"
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=key,
                translation_placeholders={"err": str(err)},
            ) from err
        except InvalidContentTypeError as err:
            key = err.translation_key if err.translation_key else "invalid_content_type"
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=key,
                translation_placeholders={"err": str(err)},
            ) from err
        except CredentialsInvalidError as err:
            key = err.translation_key if err.translation_key else "invalid_credentials"
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=key,
                translation_placeholders={"err": str(err)},
            ) from err
        except LoginError as err:
            key = err.translation_key if err.translation_key else "login_error"
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=key,
                translation_placeholders={"err": str(err)},
            ) from err
        except NoDataError as err:
            key = err.translation_key if err.translation_key else "no_data"
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=key,
                translation_placeholders={"err": str(err)},
            ) from err
        except UnexpectedDataError as err:
            key = err.translation_key if err.translation_key else "unexpected_data"
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=key,
                translation_placeholders={"err": str(err)},
            ) from err
        except NotSupportedError as err:
            key = err.translation_key if err.translation_key else "not_supported"
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=key,
                translation_placeholders={"err": str(err)},
            ) from err
        except SubscriptionError as err:
            key = err.translation_key if err.translation_key else "subscription_error"
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=key,
                translation_placeholders={"err": str(err)},
            ) from err
        except ReolinkConnectionError as err:
            key = err.translation_key if err.translation_key else "connection_error"
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=key,
                translation_placeholders={"err": str(err)},
            ) from err
        except ReolinkTimeoutError as err:
            key = err.translation_key if err.translation_key else "timeout"
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=key,
                translation_placeholders={"err": str(err)},
            ) from err
        except ReolinkError as err:
            key = err.translation_key if err.translation_key else "unexpected"
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=key,
                translation_placeholders={"err": str(err)},
            ) from err

    return decorator_raise_translated_error
