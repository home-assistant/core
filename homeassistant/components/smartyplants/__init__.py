"""The SmartyPlants integration."""

from pysmartyplants import SmartyPlantsClient

from homeassistant.const import CONF_API_KEY, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_HOST
from .coordinator import SmartyPlantsConfigEntry, SmartyPlantsCoordinator
from .webhook import async_register_webhook, async_unregister_webhook

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: SmartyPlantsConfigEntry
) -> bool:
    """Set up SmartyPlants from a config entry."""
    client = SmartyPlantsClient(
        entry.data[CONF_API_KEY],
        host=entry.data.get(CONF_HOST, DEFAULT_HOST),
        session=async_get_clientsession(hass),
    )

    coordinator = SmartyPlantsCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Registered after runtime_data is set: a push can arrive immediately.
    await async_register_webhook(hass, entry)
    entry.async_on_unload(lambda: async_unregister_webhook(hass, entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Devices exist only once the platforms have added their entities, so the
    # first name/area sync happens here rather than during the first refresh.
    coordinator.async_sync_devices()
    entry.async_on_unload(
        coordinator.async_add_listener(coordinator.async_sync_devices)
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SmartyPlantsConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
