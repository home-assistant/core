"""Services for the Kiosker integration."""

from collections.abc import Awaitable, Callable, Coroutine
import functools
from typing import Any

from kiosker import (
    AuthenticationError,
    BadRequestError,
    Blackout,
    ConnectionError,
    IPAuthenticationError,
    TLSVerificationError,
)

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .const import (
    ATTR_BACKGROUND,
    ATTR_BUTTON_BACKGROUND,
    ATTR_BUTTON_FOREGROUND,
    ATTR_BUTTON_TEXT,
    ATTR_DISMISSIBLE,
    ATTR_EXPIRE,
    ATTR_FOREGROUND,
    ATTR_ICON,
    ATTR_SOUND,
    ATTR_TEXT,
    ATTR_URL,
    ATTR_VISIBLE,
    DOMAIN,
)
from .coordinator import KioskerDataUpdateCoordinator


def handle_kiosker_api_errors(
    func: Callable[[ServiceCall], Awaitable[None]],
) -> Callable[[ServiceCall], Coroutine[Any, Any, ServiceResponse]]:
    """Decorator to handle Kiosker API errors consistently across all service calls."""

    @functools.wraps(func)
    async def wrapper(call: ServiceCall) -> ServiceResponse:
        try:
            await func(call)
        except ConnectionError as ex:
            raise HomeAssistantError(f"Unable to connect to Kiosker: {ex}") from ex
        except AuthenticationError as ex:
            raise ServiceValidationError(
                "Authentication failed. Check your API token."
            ) from ex
        except IPAuthenticationError as ex:
            raise ServiceValidationError(
                "IP authentication failed. Check your IP whitelist."
            ) from ex
        except TLSVerificationError as ex:
            raise ServiceValidationError(f"TLS verification failed: {ex}") from ex
        except BadRequestError as ex:
            raise ServiceValidationError(f"Bad request: {ex}") from ex
        else:
            return None

    return wrapper


async def _collect_coordinators(
    call: ServiceCall,
) -> list[KioskerDataUpdateCoordinator]:
    """Collect coordinators for the targeted devices."""
    registry = dr.async_get(call.hass)
    device_ids: set[str] = set()

    if ATTR_DEVICE_ID in call.data:
        direct_ids = call.data[ATTR_DEVICE_ID]
        if not isinstance(direct_ids, list):
            direct_ids = [direct_ids]
        device_ids.update(direct_ids)

    if not device_ids:
        raise HomeAssistantError("No devices targeted")

    config_entries: list[ConfigEntry] = []
    for device_id in device_ids:
        device = registry.async_get(device_id)
        if device:
            device_entries: list[ConfigEntry] = []
            for entry_id in device.config_entries:
                entry = call.hass.config_entries.async_get_entry(entry_id)
                if entry and entry.domain == DOMAIN:
                    device_entries.append(entry)
            if device_entries:
                config_entries.extend(device_entries)

    if not config_entries:
        raise HomeAssistantError(f"No {DOMAIN} devices found in targeted selection")

    coordinators: list[KioskerDataUpdateCoordinator] = []
    for config_entry in config_entries:
        if config_entry.state != ConfigEntryState.LOADED:
            raise HomeAssistantError(f"{config_entry.title} is not loaded")
        coordinators.append(config_entry.runtime_data)
    return coordinators


def _rgb_to_hex(rgb: list[int]) -> str:
    """Convert an [r, g, b] list to a hex color string."""
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


@handle_kiosker_api_errors
async def navigate_url(call: ServiceCall) -> None:
    """Navigate to a URL on the Kiosker device."""
    for coordinator in await _collect_coordinators(call):
        await call.hass.async_add_executor_job(
            coordinator.api.navigate_url, call.data[ATTR_URL]
        )


@handle_kiosker_api_errors
async def set_blackout(call: ServiceCall) -> None:
    """Set blackout mode on the Kiosker device."""
    background = _rgb_to_hex(call.data.get(ATTR_BACKGROUND, [0, 0, 0]))
    foreground = _rgb_to_hex(call.data.get(ATTR_FOREGROUND, [255, 255, 255]))
    button_background = _rgb_to_hex(
        call.data.get(ATTR_BUTTON_BACKGROUND, [255, 255, 255])
    )
    button_foreground = _rgb_to_hex(call.data.get(ATTR_BUTTON_FOREGROUND, [0, 0, 0]))

    blackout = Blackout(
        visible=call.data.get(ATTR_VISIBLE, True),
        text=call.data.get(ATTR_TEXT),
        background=background,
        foreground=foreground,
        icon=call.data.get(ATTR_ICON),
        expire=call.data.get(ATTR_EXPIRE, 60),
        dismissible=call.data.get(ATTR_DISMISSIBLE, False),
        buttonBackground=button_background,
        buttonForeground=button_foreground,
        buttonText=call.data.get(ATTR_BUTTON_TEXT),
        sound=call.data.get(ATTR_SOUND),
    )

    for coordinator in await _collect_coordinators(call):
        await call.hass.async_add_executor_job(coordinator.api.blackout_set, blackout)
        await coordinator.async_request_refresh()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Kiosker integration."""
    hass.services.async_register(DOMAIN, "navigate_url", navigate_url)
    hass.services.async_register(DOMAIN, "set_blackout", set_blackout)
