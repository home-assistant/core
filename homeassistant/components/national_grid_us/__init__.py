"""The National Grid US integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import NationalGridConfigEntry, NationalGridDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: NationalGridConfigEntry
) -> bool:
    """Set up National Grid US from a config entry."""
    coordinator = NationalGridDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Pre-register an account-level device per billing account so the meter
    # devices' via_device links resolve to an existing parent device.
    device_registry = dr.async_get(hass)
    for account_id in coordinator.data.accounts:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, account_id)},
            name=f"National Grid {account_id}",
            manufacturer="National Grid",
            entry_type=dr.DeviceEntryType.SERVICE,
            configuration_url="https://myaccount.nationalgrid.com",
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: NationalGridConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
