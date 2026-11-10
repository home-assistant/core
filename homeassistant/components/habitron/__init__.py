"""The Habitron integration."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .coordinator import HabitronConfigEntry, HbtnCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_migrate_entry(hass: HomeAssistant, entry: HabitronConfigEntry) -> None:
    """Migrate old entry data to the current version."""
    data = {**entry.data}
    if entry.version == 1 and "habitron_host" in data:
        data[CONF_HOST] = data.pop("habitron_host")
    data.pop("update_interval", None)
    # Minor bump only, so the custom integration can still load the entry.
    hass.config_entries.async_update_entry(entry, data=data, version=2, minor_version=2)


async def async_setup_entry(hass: HomeAssistant, entry: HabitronConfigEntry) -> None:
    """Set up Habitron from a config entry."""
    coordinator = HbtnCoordinator(hass, entry)
    entry.runtime_data = coordinator

    # Before the first refresh, so a failed setup still cleans up.
    entry.async_on_unload(coordinator.async_clear_router_issue)
    entry.async_on_unload(coordinator.async_close)

    # Before the update listener: moving the entry onto the hub MAC would reload it.
    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Keep polling with all sensors disabled, so the router repair issue can clear.
    entry.async_on_unload(coordinator.async_add_listener(_async_keep_polling))

    _async_cleanup_stale_devices(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


@callback
def _async_keep_polling() -> None:
    """Listen to the coordinator only so it keeps polling."""


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: HabitronConfigEntry,
    device_entry: dr.AnyDeviceEntry,
) -> bool:
    """Allow removing only devices that are no longer on the bus."""
    if config_entry.state is not ConfigEntryState.LOADED:
        return False
    coordinator = config_entry.runtime_data
    present_uids = {coordinator.uid, coordinator.router.uid}
    present_uids.update(module.uid for module in coordinator.router.modules)
    return not any(
        identifier[0] == DOMAIN and identifier[1] in present_uids
        for identifier in device_entry.identifiers
    )


async def async_unload_entry(hass: HomeAssistant, entry: HabitronConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: HabitronConfigEntry) -> None:
    """Reload the entry on update."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_cleanup_stale_devices(
    hass: HomeAssistant,
    entry: HabitronConfigEntry,
    coordinator: HbtnCoordinator,
) -> None:
    """Remove devices whose Habitron module is gone."""
    keep_uids: set[str] = {coordinator.uid, coordinator.router.uid}
    keep_uids.update(module.uid for module in coordinator.router.modules)

    dev_reg = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        # Stale only when none of its Habitron uids is on the bus.
        habitron_uids = {uid for domain, uid in device.identifiers if domain == DOMAIN}
        if habitron_uids and habitron_uids.isdisjoint(keep_uids):
            dev_reg.async_remove_device(device.id)
