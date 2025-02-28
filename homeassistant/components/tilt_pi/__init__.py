"""The Tilt Pi integration."""

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TiltPiClient
from .const import DOMAIN
from .coordinator import TiltPiConfigEntry, TiltPiDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: TiltPiConfigEntry) -> bool:
    """Set up Tilt Pi from a config entry."""
    session = async_get_clientsession(hass)
    client = TiltPiClient(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        session=session,
    )

    try:
        await client.get_hydrometers()
    except Exception as e:
        raise ConfigEntryNotReady(f"Cannot connect to Tilt Pi: {e}") from e

    coordinator = TiltPiDataUpdateCoordinator(
        hass=hass,
        config_entry=entry,
        client=client,
    )

    try:
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
    except ConfigEntryNotReady:
        await coordinator.async_shutdown()
        raise

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TiltPiConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: TiltPiDataUpdateCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()

    return unload_ok
