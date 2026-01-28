"""The Fressnapf Tracker integration."""

from fressnapftracker import AuthClient, FressnapfTrackerAuthenticationError

from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.httpx_client import get_async_client

from .const import CONF_USER_ID, DOMAIN
from .coordinator import (
    FressnapfTrackerConfigEntry,
    FressnapfTrackerDataUpdateCoordinator,
)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(
    hass: HomeAssistant, entry: FressnapfTrackerConfigEntry
) -> bool:
    """Set up Fressnapf Tracker from a config entry."""
    auth_client = AuthClient(client=get_async_client(hass))
    try:
        devices = await auth_client.get_devices(
            user_id=entry.data[CONF_USER_ID],
            user_access_token=entry.data[CONF_ACCESS_TOKEN],
        )
    except FressnapfTrackerAuthenticationError as exception:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from exception

    coordinators: list[FressnapfTrackerDataUpdateCoordinator] = []
    for device in devices:
        coordinator = FressnapfTrackerDataUpdateCoordinator(
            hass,
            entry,
            device,
        )
        await coordinator.async_config_entry_first_refresh()
        coordinators.append(coordinator)

    entry.runtime_data = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: FressnapfTrackerConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
