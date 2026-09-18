"""The SRP Energy integration."""

from srpenergy.client import SrpEnergyClient

from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .const import LOGGER
from .coordinator import SRPEnergyConfigEntry, SRPEnergyDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SRPEnergyConfigEntry) -> bool:
    """Set up the SRP Energy component from a config entry."""
    api_account_id: str = entry.data[CONF_ID]
    api_username: str = entry.data[CONF_USERNAME]
    api_password: str = entry.data[CONF_PASSWORD]

    LOGGER.debug("Configuring client using account_id %s", api_account_id)

    api_instance = SrpEnergyClient(
        api_account_id,
        api_username,
        api_password,
    )

    coordinator = SRPEnergyDataUpdateCoordinator(hass, entry, api_instance)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SRPEnergyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
