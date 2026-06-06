"""The MELCloud Home integration."""

from aiomelcloudhome import MELCloudHome, MelCloudHomeAuth

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import (
    MelCloudHomeConfigEntry,
    MelCloudHomeCoordinator,
    MelCloudHomeData,
)

PLATFORMS: list[Platform] = [Platform.CLIMATE]


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
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = MelCloudHomeData(coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MelCloudHomeConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
