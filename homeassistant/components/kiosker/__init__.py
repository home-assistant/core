"""The Kiosker integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
from urllib.parse import urlparse

from kiosker import Blackout, KioskerAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service import async_extract_referenced_entity_ids

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
    CONF_SSL,
    CONF_SSL_VERIFY,
    DOMAIN,
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
_LOGGER = logging.getLogger(__name__)
_SERVICE_REGISTRATION_LOCK = asyncio.Lock()

# Limit concurrent updates to prevent overwhelming the API
PARALLEL_UPDATES = 3


async def _get_target_coordinators(
    hass: HomeAssistant, call: ServiceCall
) -> list[KioskerDataUpdateCoordinator]:
    """Get coordinators for target devices."""
    coordinators: list[KioskerDataUpdateCoordinator] = []

    # Extract device targets from the service call
    referenced = async_extract_referenced_entity_ids(hass, call, expand_group=True)
    target_device_ids = referenced.referenced_devices

    # If no targets specified, fail the action
    if not target_device_ids:
        raise ServiceValidationError(
            "No target devices specified for Kiosker service call"
        )

    # Get device registry
    device_registry = dr.async_get(hass)

    # Create a mapping of config entry ID to coordinator for better performance
    entry_to_coordinator = {
        entry.entry_id: entry.runtime_data
        for entry in hass.config_entries.async_entries(DOMAIN)
        if hasattr(entry, "runtime_data") and entry.runtime_data
    }

    # Find coordinators for target devices
    for device_id in target_device_ids:
        device = device_registry.async_get(device_id)
        if device:
            # Find the coordinator for this device using direct lookup
            for entry_id in device.config_entries:
                if entry_id in entry_to_coordinator:
                    coordinators.append(entry_to_coordinator[entry_id])
                    break

    return coordinators


async def _call_api_safe(
    hass: HomeAssistant,
    coordinator: KioskerDataUpdateCoordinator,
    api_method: Callable,
    action_name: str,
    *args,
) -> None:
    """Call API method with error handling and logging."""
    try:
        await hass.async_add_executor_job(api_method, *args)
    except (OSError, TimeoutError) as exc:
        _LOGGER.error(
            "Failed to %s on device %s: %s", action_name, coordinator.api.host, exc
        )
    except (ValueError, TypeError) as exc:
        _LOGGER.error(
            "Invalid parameters for %s on device %s: %s",
            action_name,
            coordinator.api.host,
            exc,
        )
    except Exception:
        _LOGGER.exception(
            "Unexpected error during %s on device %s",
            action_name,
            coordinator.api.host,
        )


async def _navigate_url_handler(hass: HomeAssistant, call: ServiceCall) -> None:
    """Navigate to URL service."""
    url = call.data[ATTR_URL]

    # Validate URL format (allow any scheme including custom ones like "kiosker:")
    try:
        parsed_url = urlparse(url)
        if not parsed_url.scheme:
            raise ServiceValidationError(
                f"Invalid URL format: {url}. URL must include a scheme"
            )
        # For schemes other than http/https, we only validate basic structure
        if parsed_url.scheme in ("http", "https") and not parsed_url.netloc:
            raise ServiceValidationError(
                f"Invalid URL format: {url}. HTTP/HTTPS URLs must include domain"
            )
    except (ValueError, TypeError) as exc:
        raise ServiceValidationError(f"Failed to parse URL {url}: {exc}") from exc

    coordinators = await _get_target_coordinators(hass, call)

    for coordinator in coordinators:
        await _call_api_safe(
            hass, coordinator, coordinator.api.navigate_url, "navigate to URL", url
        )


async def _navigate_refresh_handler(hass: HomeAssistant, call: ServiceCall) -> None:
    """Refresh page service."""
    coordinators = await _get_target_coordinators(hass, call)
    for coordinator in coordinators:
        await _call_api_safe(
            hass, coordinator, coordinator.api.navigate_refresh, "navigate refresh"
        )


async def _navigate_home_handler(hass: HomeAssistant, call: ServiceCall) -> None:
    """Navigate home service."""
    coordinators = await _get_target_coordinators(hass, call)
    for coordinator in coordinators:
        await _call_api_safe(
            hass, coordinator, coordinator.api.navigate_home, "navigate home"
        )


async def _navigate_backward_handler(hass: HomeAssistant, call: ServiceCall) -> None:
    """Navigate backward service."""
    coordinators = await _get_target_coordinators(hass, call)
    for coordinator in coordinators:
        await _call_api_safe(
            hass,
            coordinator,
            coordinator.api.navigate_backward,
            "navigate backward",
        )


async def _navigate_forward_handler(hass: HomeAssistant, call: ServiceCall) -> None:
    """Navigate forward service."""
    coordinators = await _get_target_coordinators(hass, call)
    for coordinator in coordinators:
        await _call_api_safe(
            hass, coordinator, coordinator.api.navigate_forward, "navigate forward"
        )


async def _print_page_handler(hass: HomeAssistant, call: ServiceCall) -> None:
    """Print page service."""
    coordinators = await _get_target_coordinators(hass, call)
    for coordinator in coordinators:
        await _call_api_safe(hass, coordinator, coordinator.api.print, "print page")


async def _clear_cookies_handler(hass: HomeAssistant, call: ServiceCall) -> None:
    """Clear cookies service."""
    coordinators = await _get_target_coordinators(hass, call)
    for coordinator in coordinators:
        await _call_api_safe(
            hass, coordinator, coordinator.api.clear_cookies, "clear cookies"
        )


async def _clear_cache_handler(hass: HomeAssistant, call: ServiceCall) -> None:
    """Clear cache service."""
    coordinators = await _get_target_coordinators(hass, call)
    for coordinator in coordinators:
        await _call_api_safe(
            hass, coordinator, coordinator.api.clear_cache, "clear cache"
        )


async def _screensaver_interact_handler(hass: HomeAssistant, call: ServiceCall) -> None:
    """Interact with screensaver service."""
    coordinators = await _get_target_coordinators(hass, call)
    for coordinator in coordinators:
        await _call_api_safe(
            hass,
            coordinator,
            coordinator.api.screensaver_interact,
            "screensaver interact",
        )


async def _blackout_set_handler(hass: HomeAssistant, call: ServiceCall) -> None:
    """Set blackout service."""
    if Blackout is None:
        return

    coordinators = await _get_target_coordinators(hass, call)

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
        expire=call.data.get(ATTR_EXPIRE, 60),
        dismissible=call.data.get(ATTR_DISMISSIBLE, False),
        buttonBackground=button_background_color,
        buttonForeground=button_foreground_color,
        buttonText=call.data.get(ATTR_BUTTON_TEXT, None),
        sound=call.data.get(ATTR_SOUND, 0),
    )

    for coordinator in coordinators:
        await _call_api_safe(
            hass,
            coordinator,
            coordinator.api.blackout_set,
            "blackout set",
            blackout,
        )
        await coordinator.async_request_refresh()


async def _blackout_clear_handler(hass: HomeAssistant, call: ServiceCall) -> None:
    """Clear blackout service."""
    coordinators = await _get_target_coordinators(hass, call)
    for coordinator in coordinators:
        await _call_api_safe(
            hass, coordinator, coordinator.api.blackout_clear, "blackout clear"
        )
        await coordinator.async_request_refresh()


async def _register_services(hass: HomeAssistant) -> None:
    """Register Kiosker services."""

    async def navigate_url(call: ServiceCall) -> None:
        """Navigate to URL service."""
        await _navigate_url_handler(hass, call)

    async def navigate_refresh(call: ServiceCall) -> None:
        """Refresh page service."""
        await _navigate_refresh_handler(hass, call)

    async def navigate_home(call: ServiceCall) -> None:
        """Navigate home service."""
        await _navigate_home_handler(hass, call)

    async def navigate_backward(call: ServiceCall) -> None:
        """Navigate backward service."""
        await _navigate_backward_handler(hass, call)

    async def navigate_forward(call: ServiceCall) -> None:
        """Navigate forward service."""
        await _navigate_forward_handler(hass, call)

    async def print_page(call: ServiceCall) -> None:
        """Print page service."""
        await _print_page_handler(hass, call)

    async def clear_cookies(call: ServiceCall) -> None:
        """Clear cookies service."""
        await _clear_cookies_handler(hass, call)

    async def clear_cache(call: ServiceCall) -> None:
        """Clear cache service."""
        await _clear_cache_handler(hass, call)

    async def screensaver_interact(call: ServiceCall) -> None:
        """Interact with screensaver service."""
        await _screensaver_interact_handler(hass, call)

    async def blackout_set(call: ServiceCall) -> None:
        """Set blackout service."""
        await _blackout_set_handler(hass, call)

    async def blackout_clear(call: ServiceCall) -> None:
        """Clear blackout service."""
        await _blackout_clear_handler(hass, call)

    # Register services
    hass.services.async_register(DOMAIN, SERVICE_NAVIGATE_URL, navigate_url)
    hass.services.async_register(DOMAIN, SERVICE_NAVIGATE_REFRESH, navigate_refresh)
    hass.services.async_register(DOMAIN, SERVICE_NAVIGATE_HOME, navigate_home)
    hass.services.async_register(DOMAIN, SERVICE_NAVIGATE_BACKWARD, navigate_backward)
    hass.services.async_register(DOMAIN, SERVICE_NAVIGATE_FORWARD, navigate_forward)
    hass.services.async_register(DOMAIN, SERVICE_PRINT, print_page)
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_COOKIES, clear_cookies)
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_CACHE, clear_cache)
    hass.services.async_register(
        DOMAIN, SERVICE_SCREENSAVER_INTERACT, screensaver_interact
    )
    hass.services.async_register(DOMAIN, SERVICE_BLACKOUT_SET, blackout_set)
    hass.services.async_register(DOMAIN, SERVICE_BLACKOUT_CLEAR, blackout_clear)


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
        try:
            # Convert RGB list [r, g, b] to hex format with bounds checking
            r, g, b = [max(0, min(255, int(x))) for x in color]
        except (ValueError, TypeError) as exc:
            _LOGGER.warning(
                "Invalid RGB color values %s: %s. Using default color", color, exc
            )
            return "#000000"
        else:
            return f"#{r:02x}{g:02x}{b:02x}"
    # Fallback to default if conversion fails
    _LOGGER.warning(
        "Invalid color format %s. Expected string or list of 3 integers", color
    )
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
        entry,
    )

    await coordinator.async_config_entry_first_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    # Register services globally (only once) - use lock to prevent race conditions
    async with _SERVICE_REGISTRATION_LOCK:
        if not hass.services.has_service(DOMAIN, SERVICE_NAVIGATE_URL):
            await _register_services(hass)

    return True


def _remove_service_safe(hass: HomeAssistant, domain: str, service: str) -> None:
    """Safely remove a service if it exists."""
    if hass.services.has_service(domain, service):
        hass.services.async_remove(domain, service)
        _LOGGER.debug("Removed service %s.%s", domain, service)
    else:
        _LOGGER.debug("Service %s.%s does not exist, skipping removal", domain, service)


async def async_unload_entry(hass: HomeAssistant, entry: KioskerConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)

    # Only remove services if this is the last kiosker entry
    if len(hass.config_entries.async_entries(DOMAIN)) == 1:
        # List of all services to remove
        services_to_remove = [
            SERVICE_NAVIGATE_URL,
            SERVICE_NAVIGATE_REFRESH,
            SERVICE_NAVIGATE_HOME,
            SERVICE_NAVIGATE_BACKWARD,
            SERVICE_NAVIGATE_FORWARD,
            SERVICE_PRINT,
            SERVICE_CLEAR_COOKIES,
            SERVICE_CLEAR_CACHE,
            SERVICE_SCREENSAVER_INTERACT,
            SERVICE_BLACKOUT_SET,
            SERVICE_BLACKOUT_CLEAR,
        ]

        # Remove each service safely
        for service in services_to_remove:
            _remove_service_safe(hass, DOMAIN, service)

    return unload_ok
