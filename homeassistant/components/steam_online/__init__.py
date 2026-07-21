"""The Steam integration."""

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import CONF_ACCOUNTS, DOMAIN, SUBENTRY_TYPE_FRIEND
from .coordinator import SteamConfigEntry, SteamDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SteamConfigEntry) -> bool:
    """Set up Steam from a config entry."""
    coordinator = SteamDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: SteamConfigEntry) -> None:
    """Handle update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SteamConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: SteamConfigEntry) -> bool:
    """Migrate old entry."""

    if entry.version < 2:
        # Migrate entity unique id

        @callback
        def migrate_unique_id(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
            if entity_entry.unique_id.startswith("sensor.steam_"):
                new = entity_entry.unique_id.removeprefix("sensor.steam_") + "_account"
                return {"new_unique_id": new}
            return None

        await er.async_migrate_entries(hass, entry.entry_id, migrate_unique_id)
        hass.config_entries.async_update_entry(entry, version=2)

    if entry.version < 3:
        for steamid, name in entry.options[CONF_ACCOUNTS].items():
            if steamid == entry.unique_id:
                continue
            subentry = ConfigSubentry(
                subentry_type=SUBENTRY_TYPE_FRIEND,
                title=name,
                unique_id=steamid,
                data={},  # type: ignore[arg-type]
            )
            hass.config_entries.async_add_subentry(entry, subentry)

        dev_reg = dr.async_get(hass)
        if device := dev_reg.async_get_device_by_identifier(
            (DOMAIN, entry.entry_id), entry.entry_id
        ):
            if TYPE_CHECKING:
                assert entry.unique_id
            dev_reg.async_update_device(
                device.id, new_identifiers={(DOMAIN, entry.unique_id)}
            )
        hass.config_entries.async_update_entry(entry, version=3, options={})
    return True
