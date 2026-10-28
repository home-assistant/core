"""The WATERCryst integration."""

from pyocat import AsyncApiClient, AsyncAuth

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from .coordinator import (
    WatercrystMeasurementsCoordinator,
    WatercrystStateCoordinator,
    WatercrystUpdateCoordinator,
)

_PLATFORMS: list[Platform] = [Platform.SENSOR]


type WatercrystConfigEntry = ConfigEntry[WatercrystUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: WatercrystConfigEntry) -> None:
    """Set up a WATERCryst BIOCAT device from a config entry."""

    client = AsyncApiClient(
        auth=AsyncAuth(client=get_async_client(hass), api_key=entry.data[CONF_API_KEY])
    )

    state = WatercrystStateCoordinator(hass, entry, client)
    measurements = WatercrystMeasurementsCoordinator(hass, entry, client)
    coordinator = WatercrystUpdateCoordinator(hass, entry, client, state, measurements)

    await coordinator.async_config_entry_first_refresh()
    await state.async_config_entry_first_refresh()
    await measurements.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: WatercrystConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, _PLATFORMS)
