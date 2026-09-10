"""The MELCloud Home integration."""

from aiomelcloudhome import MELCloudHome, MelCloudHomeAuth

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import (
    MelCloudHomeConfigEntry,
    MelCloudHomeCoordinator,
    MelCloudHomeEnergyCoordinator,
    MelCloudHomeRuntimeData,
)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(
    hass: HomeAssistant, entry: MelCloudHomeConfigEntry
) -> bool:
    """Set up MELCloud Home from a config entry."""
    session = async_get_clientsession(hass)
    auth = MelCloudHomeAuth(
        username=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        session=session,
    )
    client = MELCloudHome(auth=auth, session=session)

    coordinator = MelCloudHomeCoordinator(hass, entry, client)
    energy_coordinator = MelCloudHomeEnergyCoordinator(hass, entry, client)

    # It has to be this order, to avoid a race condition
    await coordinator.async_config_entry_first_refresh()
    await energy_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = MelCloudHomeRuntimeData(
        coordinator=coordinator, energy_coordinator=energy_coordinator
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MelCloudHomeConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
