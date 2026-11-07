"""Integrate Dobiss NXT light outputs."""

from dobiss_nxt import DobissClient

from homeassistant.const import CONF_HOST, CONF_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_API_SECRET, DOMAIN
from .coordinator import DobissConfigEntry, DobissCoordinator

PLATFORMS = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: DobissConfigEntry) -> None:
    """Set up a controller, validating connectivity before adding entities."""
    client = DobissClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_API_SECRET],
        secure=entry.data[CONF_SSL],
    )
    coordinator = DobissCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Dobiss",
        model="NXT",
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: DobissConfigEntry) -> None:
    """Unload the controller and coordinator listeners."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
