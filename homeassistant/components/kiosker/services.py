"""Services for the Kiosker integration."""

from collections.abc import Awaitable, Callable, Coroutine
from enum import StrEnum
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
import probatio

from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, selector, service

from .const import DOMAIN
from .coordinator import KioskerConfigEntry, KioskerDataUpdateCoordinator


class KioskerService(StrEnum):
    """Store keys for Kiosker services."""

    NAVIGATE_URL = "navigate_url"
    SET_BLACKOUT = "set_blackout"


class KioskerServiceArgument(StrEnum):
    """Store keys for Kiosker service arguments."""

    URL = "url"
    VISIBLE = "visible"
    TEXT = "text"
    BACKGROUND = "background"
    FOREGROUND = "foreground"
    ICON = "icon"
    EXPIRE = "expire"
    DISMISSIBLE = "dismissible"
    BUTTON_BACKGROUND = "button_background"
    BUTTON_FOREGROUND = "button_foreground"
    BUTTON_TEXT = "button_text"
    SOUND = "sound"


NAVIGATE_URL_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.DEVICE_ID): str,
        probatio.Required(KioskerServiceArgument.URL): str,
    }
)

SET_BLACKOUT_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.DEVICE_ID): str,
        probatio.Optional(KioskerServiceArgument.VISIBLE, default=True): cv.boolean,
        probatio.Optional(KioskerServiceArgument.TEXT): str,
        probatio.Optional(
            KioskerServiceArgument.BACKGROUND, default=[0, 0, 0]
        ): selector.ColorRGBSelector(),
        probatio.Optional(
            KioskerServiceArgument.FOREGROUND, default=[255, 255, 255]
        ): selector.ColorRGBSelector(),
        probatio.Optional(KioskerServiceArgument.ICON): str,
        probatio.Optional(KioskerServiceArgument.EXPIRE, default=60): probatio.All(
            probatio.Coerce(int), probatio.Range(min=0, max=100000)
        ),
        probatio.Optional(
            KioskerServiceArgument.DISMISSIBLE, default=False
        ): cv.boolean,
        probatio.Optional(
            KioskerServiceArgument.BUTTON_BACKGROUND, default=[255, 255, 255]
        ): selector.ColorRGBSelector(),
        probatio.Optional(
            KioskerServiceArgument.BUTTON_FOREGROUND, default=[0, 0, 0]
        ): selector.ColorRGBSelector(),
        probatio.Optional(KioskerServiceArgument.BUTTON_TEXT): str,
        probatio.Optional(KioskerServiceArgument.SOUND): str,
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


async def _get_coordinator(
    call: ServiceCall,
) -> KioskerDataUpdateCoordinator:
    """Get the coordinator for the targeted device."""
    config_entry: KioskerConfigEntry
    _, config_entry = service.async_get_device_and_config_entry(
        call.hass, DOMAIN, call.data[CommonServiceArgument.DEVICE_ID]
    )
    return config_entry.runtime_data


def _rgb_to_hex(rgb: list[int]) -> str:
    """Convert an [r, g, b] list to a hex color string."""
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


@handle_kiosker_api_errors
async def navigate_url(call: ServiceCall) -> None:
    """Navigate to a URL on the Kiosker device."""
    coordinator = await _get_coordinator(call)
    await call.hass.async_add_executor_job(
        coordinator.api.navigate_url, call.data[KioskerServiceArgument.URL]
    )


@handle_kiosker_api_errors
async def set_blackout(call: ServiceCall) -> None:
    """Set blackout mode on the Kiosker device."""
    blackout = Blackout(
        visible=call.data[KioskerServiceArgument.VISIBLE],
        text=call.data.get(KioskerServiceArgument.TEXT),
        background=_rgb_to_hex(call.data[KioskerServiceArgument.BACKGROUND]),
        foreground=_rgb_to_hex(call.data[KioskerServiceArgument.FOREGROUND]),
        icon=call.data.get(KioskerServiceArgument.ICON),
        expire=call.data[KioskerServiceArgument.EXPIRE],
        dismissible=call.data[KioskerServiceArgument.DISMISSIBLE],
        buttonBackground=_rgb_to_hex(
            call.data[KioskerServiceArgument.BUTTON_BACKGROUND]
        ),
        buttonForeground=_rgb_to_hex(
            call.data[KioskerServiceArgument.BUTTON_FOREGROUND]
        ),
        buttonText=call.data.get(KioskerServiceArgument.BUTTON_TEXT),
        sound=call.data.get(KioskerServiceArgument.SOUND),
    )

    coordinator = await _get_coordinator(call)
    await call.hass.async_add_executor_job(coordinator.api.blackout_set, blackout)
    await coordinator.async_request_refresh()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Kiosker integration."""
    hass.services.async_register(
        DOMAIN, KioskerService.NAVIGATE_URL, navigate_url, schema=NAVIGATE_URL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, KioskerService.SET_BLACKOUT, set_blackout, schema=SET_BLACKOUT_SCHEMA
    )
