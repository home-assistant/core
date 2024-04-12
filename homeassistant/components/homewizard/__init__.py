"""The Homewizard integration."""

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, LOGGER, PLATFORMS
from .coordinator import HWEnergyDeviceUpdateCoordinator as Coordinator


async def _async_migrate_entries(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Migrate old entry.

    The HWE-SKT had no total_power_*_kwh in 2023.11, in 2023.12 it does.
    But simultaneously, the total_power_*_t1_kwh was removed for HWE-SKT.

    This migration migrates the old unique_id to the new one, if possible.

    Migration can be removed after 2024.6
    """
    entity_registry = er.async_get(hass)

    @callback
    def update_unique_id(entry: er.RegistryEntry) -> dict[str, str] | None:
        replacements = {
            "total_power_import_t1_kwh": "total_power_import_kwh",
            "total_power_export_t1_kwh": "total_power_export_kwh",
        }

        for old_id, new_id in replacements.items():
            if entry.unique_id.endswith(old_id):
                new_unique_id = entry.unique_id.replace(old_id, new_id)
                if existing_entity_id := entity_registry.async_get_entity_id(
                    entry.domain, entry.platform, new_unique_id
                ):
                    LOGGER.debug(
                        "Cannot migrate to unique_id '%s', already exists for '%s'",
                        new_unique_id,
                        existing_entity_id,
                    )
                    return None
                LOGGER.debug(
                    "Migrating entity '%s' unique_id from '%s' to '%s'",
                    entry.entity_id,
                    entry.unique_id,
                    new_unique_id,
                )
                return {
                    "new_unique_id": new_unique_id,
                }

        return None

    await er.async_migrate_entries(hass, config_entry.entry_id, update_unique_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Homewizard from a config entry."""
    coordinator = Coordinator(hass)
    try:
        await coordinator.async_config_entry_first_refresh()

    except ConfigEntryNotReady:
        await coordinator.api.close()

        if coordinator.api_disabled:
            entry.async_start_reauth(hass)

        raise

    await _async_migrate_entries(hass, entry)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Abort reauth config flow if active
    for progress_flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN):
        if (
            "context" in progress_flow
            and progress_flow["context"].get("source") == SOURCE_REAUTH
        ):
            hass.config_entries.flow.async_abort(progress_flow["flow_id"])

    # Finalize
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.api.close()
    return unload_ok
