"""The Kiosker integration."""

from __future__ import annotations

from kiosker import Blackout, KioskerAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady

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
    CONF_API_TOKEN,
    CONF_POLL_INTERVAL,
    CONF_SSL,
    CONF_SSL_VERIFY,
    SERVICE_BLACKOUT_CLEAR,
    SERVICE_BLACKOUT_SET,
    SERVICE_CLEAR_CACHE,
    SERVICE_CLEAR_COOKIES,
    SERVICE_NAVIGATE_BACKWARD,
    SERVICE_NAVIGATE_FORWARD,
    SERVICE_NAVIGATE_HOME,
    SERVICE_NAVIGATE_REFRESH,
    SERVICE_NAVIGATE_URL,
    SERVICE_PRINT,
    SERVICE_SCREENSAVER_INTERACT,
)
from .coordinator import KioskerDataUpdateCoordinator

_PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH]

type KioskerConfigEntry = ConfigEntry[KioskerDataUpdateCoordinator]


def convert_rgb_to_hex(color: str | list[int]) -> str:
    """Convert RGB color to hex format."""
    if isinstance(color, str):
        # If already a string, assume it's hex or named color
        if color.startswith("#"):
            return color
        # Handle named colors or other formats
        return color
    if isinstance(color, list) and len(color) == 3:
        # Convert RGB list [r, g, b] to hex format
        r, g, b = [int(x) for x in color]
        return f"#{r:02x}{g:02x}{b:02x}"
    # Fallback to default if conversion fails
    return "#000000"


async def async_setup_entry(hass: HomeAssistant, entry: KioskerConfigEntry) -> bool:
    """Set up Kiosker from a config entry."""
    if KioskerAPI is None:
        raise ConfigEntryNotReady("Kiosker dependency not available")

    api = KioskerAPI(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        token=entry.data[CONF_API_TOKEN],
        ssl=entry.data.get(CONF_SSL, False),
        verify=entry.data.get(CONF_SSL_VERIFY, False),
    )

    coordinator = KioskerDataUpdateCoordinator(
        hass,
        api,
        entry.data[CONF_POLL_INTERVAL],
    )

    await coordinator.async_config_entry_first_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    # Register services
    async def navigate_url(call: ServiceCall) -> None:
        """Navigate to URL service."""
        url = call.data[ATTR_URL]
        await hass.async_add_executor_job(api.navigate_url, url)

    async def navigate_refresh(call: ServiceCall) -> None:
        """Refresh page service."""
        await hass.async_add_executor_job(api.navigate_refresh)

    async def navigate_home(call: ServiceCall) -> None:
        """Navigate home service."""
        await hass.async_add_executor_job(api.navigate_home)

    async def navigate_backward(call: ServiceCall) -> None:
        """Navigate backward service."""
        await hass.async_add_executor_job(api.navigate_backward)

    async def navigate_forward(call: ServiceCall) -> None:
        """Navigate forward service."""
        await hass.async_add_executor_job(api.navigate_forward)

    async def print_page(call: ServiceCall) -> None:
        """Print page service."""
        await hass.async_add_executor_job(api.print)

    async def clear_cookies(call: ServiceCall) -> None:
        """Clear cookies service."""
        await hass.async_add_executor_job(api.clear_cookies)

    async def clear_cache(call: ServiceCall) -> None:
        """Clear cache service."""
        await hass.async_add_executor_job(api.clear_cache)

    async def screensaver_interact(call: ServiceCall) -> None:
        """Interact with screensaver service."""
        await hass.async_add_executor_job(api.screensaver_interact)

    async def blackout_set(call: ServiceCall) -> None:
        """Set blackout service."""
        if Blackout is None:
            return

        # Convert RGB values to hex format
        background_color = convert_rgb_to_hex(call.data.get(ATTR_BACKGROUND, "#000000"))
        foreground_color = convert_rgb_to_hex(call.data.get(ATTR_FOREGROUND, "#FFFFFF"))
        button_background_color = convert_rgb_to_hex(
            call.data.get(ATTR_BUTTON_BACKGROUND, "#FFFFFF")
        )
        button_foreground_color = convert_rgb_to_hex(
            call.data.get(ATTR_BUTTON_FOREGROUND, "#000000")
        )

        blackout = Blackout(
            visible=call.data.get(ATTR_VISIBLE, True),
            text=call.data.get(ATTR_TEXT, ""),
            background=background_color,
            foreground=foreground_color,
            icon=call.data.get(ATTR_ICON, ""),
            expire=call.data.get(ATTR_EXPIRE, 0),
            dismissible=call.data.get(ATTR_DISMISSIBLE, False),
            buttonBackground=button_background_color,
            buttonForeground=button_foreground_color,
            buttonText=call.data.get(ATTR_BUTTON_TEXT, None),
            sound=call.data.get(ATTR_SOUND, None),
        )
        await hass.async_add_executor_job(api.blackout_set, blackout)

    async def blackout_clear(call: ServiceCall) -> None:
        """Clear blackout service."""
        await hass.async_add_executor_job(api.blackout_clear)
        await coordinator.async_request_refresh()

    hass.services.async_register("kiosker", SERVICE_NAVIGATE_URL, navigate_url)
    hass.services.async_register("kiosker", SERVICE_NAVIGATE_REFRESH, navigate_refresh)
    hass.services.async_register("kiosker", SERVICE_NAVIGATE_HOME, navigate_home)
    hass.services.async_register(
        "kiosker", SERVICE_NAVIGATE_BACKWARD, navigate_backward
    )
    hass.services.async_register("kiosker", SERVICE_NAVIGATE_FORWARD, navigate_forward)
    hass.services.async_register("kiosker", SERVICE_PRINT, print_page)
    hass.services.async_register("kiosker", SERVICE_CLEAR_COOKIES, clear_cookies)
    hass.services.async_register("kiosker", SERVICE_CLEAR_CACHE, clear_cache)
    hass.services.async_register(
        "kiosker", SERVICE_SCREENSAVER_INTERACT, screensaver_interact
    )
    hass.services.async_register("kiosker", SERVICE_BLACKOUT_SET, blackout_set)
    hass.services.async_register("kiosker", SERVICE_BLACKOUT_CLEAR, blackout_clear)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: KioskerConfigEntry) -> bool:
    """Unload a config entry."""
    # Remove services
    hass.services.async_remove("kiosker", SERVICE_NAVIGATE_URL)
    hass.services.async_remove("kiosker", SERVICE_NAVIGATE_REFRESH)
    hass.services.async_remove("kiosker", SERVICE_NAVIGATE_HOME)
    hass.services.async_remove("kiosker", SERVICE_NAVIGATE_BACKWARD)
    hass.services.async_remove("kiosker", SERVICE_NAVIGATE_FORWARD)
    hass.services.async_remove("kiosker", SERVICE_PRINT)
    hass.services.async_remove("kiosker", SERVICE_CLEAR_COOKIES)
    hass.services.async_remove("kiosker", SERVICE_CLEAR_CACHE)
    hass.services.async_remove("kiosker", SERVICE_SCREENSAVER_INTERACT)
    hass.services.async_remove("kiosker", SERVICE_BLACKOUT_SET)
    hass.services.async_remove("kiosker", SERVICE_BLACKOUT_CLEAR)

    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
