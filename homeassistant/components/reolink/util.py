"""Utility functions for the Reolink component."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from typing import Any, ParamSpec, TypeVar

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
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .host import ReolinkHost

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
        ch = host.api.channel_for_uid(device_uid[1])
    return (device_uid, ch, is_chime)


T = TypeVar("T")
P = ParamSpec("P")


# Decorators
def raise_translated_error(
    func: Callable[P, Awaitable[T]],
) -> Callable[P, Coroutine[Any, Any, T]]:
    """Wrap a reolink-aio function to translate any potential errors."""

    async def decorator_raise_translated_error(*args: P.args, **kwargs: P.kwargs) -> T:
        """Try a reolink-aio function and translate any potential errors."""
        try:
            return await func(*args, **kwargs)
        except InvalidParameterError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_parameter",
                translation_placeholders={"err": str(err)},
            ) from err
        except ApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={"err": str(err)},
            ) from err
        except InvalidContentTypeError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_content_type",
                translation_placeholders={"err": str(err)},
            ) from err
        except CredentialsInvalidError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_credentials",
                translation_placeholders={"err": str(err)},
            ) from err
        except LoginError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="login_error",
                translation_placeholders={"err": str(err)},
            ) from err
        except NoDataError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="no_data",
                translation_placeholders={"err": str(err)},
            ) from err
        except UnexpectedDataError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unexpected_data",
                translation_placeholders={"err": str(err)},
            ) from err
        except NotSupportedError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="not_supported",
                translation_placeholders={"err": str(err)},
            ) from err
        except SubscriptionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="subscription_error",
                translation_placeholders={"err": str(err)},
            ) from err
        except ReolinkConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="connection_error",
                translation_placeholders={"err": str(err)},
            ) from err
        except ReolinkTimeoutError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="timeout",
                translation_placeholders={"err": str(err)},
            ) from err
        except ReolinkError as err:
            raise HomeAssistantError(err) from err

    return decorator_raise_translated_error
