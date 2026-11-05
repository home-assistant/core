"""The SmartyPlants integration."""

from pysmartyplants import SmartyPlantsClient

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import SmartyPlantsConfigEntry, SmartyPlantsCoordinator
from .webhook import async_register_webhook, async_unregister_webhook

PLATFORMS: list[Platform] = [Platform.SENSOR]

# The custom integration this one replaces named the fertiliser countdown
# differently. Renaming its registry entry keeps the user's entity id alive.
_LEGACY_SUFFIX = "_fertilise_days"
_NEW_SUFFIX = "_fertilize"


async def async_setup_entry(
    hass: HomeAssistant, entry: SmartyPlantsConfigEntry
) -> None:
    """Set up SmartyPlants from a config entry."""
    await _async_migrate_legacy_unique_ids(hass, entry)

    client = SmartyPlantsClient(
        entry.data[CONF_API_KEY],
        session=async_get_clientsession(hass),
    )

    coordinator = SmartyPlantsCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Registered after runtime_data is set: a push can arrive immediately.
    await async_register_webhook(hass, entry)
    entry.async_on_unload(lambda: async_unregister_webhook(hass, entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def _async_migrate_legacy_unique_ids(
    hass: HomeAssistant, entry: SmartyPlantsConfigEntry
) -> None:
    """Adopt entity registry entries left behind by the custom integration."""
    registry = er.async_get(hass)

    @callback
    def _migrate(registry_entry: er.RegistryEntry) -> dict[str, str] | None:
        if not registry_entry.unique_id.endswith(_LEGACY_SUFFIX):
            return None
        new_unique_id = (
            registry_entry.unique_id.removesuffix(_LEGACY_SUFFIX) + _NEW_SUFFIX
        )
        # Both ids exist when the user already ran this integration once, and
        # claiming a taken unique id would abort setup.
        if registry.async_get_entity_id(registry_entry.domain, DOMAIN, new_unique_id):
            return None
        return {"new_unique_id": new_unique_id}

    await er.async_migrate_entries(hass, entry.entry_id, _migrate)


async def async_unload_entry(
    hass: HomeAssistant, entry: SmartyPlantsConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
