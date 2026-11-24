"""Support for Hinen Power."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .auth_config import AsyncConfigEntryAuth
from .coordinator import (
    HinenDataUpdateCoordinator,
    HinenPowerConfigEntry,
    HinenPowerRuntimeData,
)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: HinenPowerConfigEntry) -> None:
    """Set up the Hinen Power integration."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    auth = AsyncConfigEntryAuth(hass, OAuth2Session(hass, entry, implementation))
    await auth.check_and_refresh_token()

    coordinator = HinenDataUpdateCoordinator(hass, entry, auth)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = HinenPowerRuntimeData(
        coordinator=coordinator,
        auth=auth,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: HinenPowerConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
