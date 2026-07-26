"""The energieleser integration."""

from energieleser import EnergieleserClient

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import EnergieleserConfigEntry, EnergieleserCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: EnergieleserConfigEntry
) -> bool:
    """Set up energieleser from a config entry."""
    client = EnergieleserClient(
        host=entry.data[CONF_HOST],
        session=async_get_clientsession(hass),
    )
    coordinator = EnergieleserCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: EnergieleserConfigEntry
) -> bool:
    """Unload an energieleser config entry."""
    ir.async_delete_issue(hass, DOMAIN, f"pin_locked_{entry.entry_id}")
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
