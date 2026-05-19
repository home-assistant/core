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
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

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

_RGB_COLOR = vol.All(
    list,
    vol.Length(min=3, max=3),
    [vol.All(vol.Coerce(int), vol.Range(min=0, max=255))],
)

NAVIGATE_URL_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): vol.Any(str, [str]),
        vol.Required(ATTR_URL): str,
    }
)

SET_BLACKOUT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): vol.Any(str, [str]),
        vol.Optional(ATTR_VISIBLE, default=True): cv.boolean,
        vol.Optional(ATTR_TEXT): str,
        vol.Optional(ATTR_BACKGROUND, default=[0, 0, 0]): _RGB_COLOR,
        vol.Optional(ATTR_FOREGROUND, default=[255, 255, 255]): _RGB_COLOR,
        vol.Optional(ATTR_ICON): str,
        vol.Optional(ATTR_EXPIRE, default=60): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100000)
        ),
        vol.Optional(ATTR_DISMISSIBLE, default=False): cv.boolean,
        vol.Optional(ATTR_BUTTON_BACKGROUND, default=[255, 255, 255]): _RGB_COLOR,
        vol.Optional(ATTR_BUTTON_FOREGROUND, default=[0, 0, 0]): _RGB_COLOR,
        vol.Optional(ATTR_BUTTON_TEXT): str,
        vol.Optional(ATTR_SOUND): str,
    }
)


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
    blackout = Blackout(
        visible=call.data[ATTR_VISIBLE],
        text=call.data.get(ATTR_TEXT),
        background=_rgb_to_hex(call.data[ATTR_BACKGROUND]),
        foreground=_rgb_to_hex(call.data[ATTR_FOREGROUND]),
        icon=call.data.get(ATTR_ICON),
        expire=call.data[ATTR_EXPIRE],
        dismissible=call.data[ATTR_DISMISSIBLE],
        buttonBackground=_rgb_to_hex(call.data[ATTR_BUTTON_BACKGROUND]),
        buttonForeground=_rgb_to_hex(call.data[ATTR_BUTTON_FOREGROUND]),
        buttonText=call.data.get(ATTR_BUTTON_TEXT),
        sound=call.data.get(ATTR_SOUND),
    )

    for coordinator in await _collect_coordinators(call):
        await call.hass.async_add_executor_job(coordinator.api.blackout_set, blackout)
        await coordinator.async_request_refresh()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Kiosker integration."""
    hass.services.async_register(
        DOMAIN, "navigate_url", navigate_url, schema=NAVIGATE_URL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "set_blackout", set_blackout, schema=SET_BLACKOUT_SCHEMA
    )
