"""The Habitron integration."""

import logging

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .coordinator import HabitronConfigEntry, HbtnCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_migrate_entry(hass: HomeAssistant, entry: HabitronConfigEntry) -> bool:
    """Migrate an old config entry.

    Version 1 stored the host under the integration-specific ``habitron_host``
    key; version 2 uses Home Assistant's shared ``CONF_HOST``.

    The change below is a *minor* bump on purpose. The custom (HACS)
    integration numbers its entries 2 as well, and Home Assistant refuses an
    entry whose **major** version is higher than the handler's -- so raising
    the major here would leave anyone who tries this integration unable to go
    back to the custom one, with the entry refused outright. A higher minor
    still triggers this migration but keeps that path open, which matters while
    both exist side by side.

    ``websock_token`` is deliberately kept. It is a real setting, not a
    leftover: a SmartHub running on its own machine reaches Home Assistant over
    a websocket and authenticates with a long-lived token, where a hub sharing
    the machine uses the supervisor token and needs none. This first version
    does not expose the field because it implements no path that reads it, but
    the custom integration does -- from this very entry -- and a later PR here
    will. Dropping it would strand both.
    """
    data = {**entry.data}
    if entry.version == 1 and "habitron_host" in data:
        data[CONF_HOST] = data.pop("habitron_host")
    # ``update_interval`` predates the move to a fixed ``SCAN_INTERVAL`` and is
    # read by neither integration.
    data.pop("update_interval", None)
    hass.config_entries.async_update_entry(entry, data=data, version=2, minor_version=2)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HabitronConfigEntry) -> bool:
    """Set up Habitron from a config entry."""
    coordinator = HbtnCoordinator(hass, entry)
    entry.runtime_data = coordinator

    # Registered before the first refresh, not in ``async_unload_entry``: a
    # setup that fails runs the on-unload callbacks but never
    # ``async_unload_entry``, so cleanup living only there would leave the
    # client open and the router repair issue standing on every retry.
    entry.async_on_unload(coordinator.async_clear_router_issue)
    entry.async_on_unload(coordinator.async_close)

    # First refresh runs the coordinator setup (connect, build the hub and bus
    # models, register the devices), then the first bus poll. Both halves are
    # wrapped by DataUpdateCoordinator, which turns every failure into
    # ConfigEntryNotReady and carries the translation key the coordinator
    # attached -- so no raw library error can surface here.
    await coordinator.async_config_entry_first_refresh()

    # Before the update listener exists: adopting rewrites the entry, and
    # ``async_update_entry`` fires the listeners -- which would schedule a
    # reload while this very setup is still running.
    _async_adopt_hub_identity(hass, entry, coordinator)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    _async_cleanup_stale_devices(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: HabitronConfigEntry,
    device_entry: dr.AnyDeviceEntry,
) -> bool:
    """Allow removing only devices whose Habitron member is gone from the bus.

    The hub, the router and every module still present in the current model are
    live devices and must not be deleted by hand; only a device whose uid no
    longer exists on the bus (a leftover of a removed module) may be removed.
    """
    coordinator = config_entry.runtime_data
    present_uids = {coordinator.uid, coordinator.router.uid}
    present_uids.update(module.uid for module in coordinator.router.modules)
    return not any(
        identifier[0] == DOMAIN and identifier[1] in present_uids
        for identifier in device_entry.identifiers
    )


async def async_unload_entry(hass: HomeAssistant, entry: HabitronConfigEntry) -> bool:
    """Unload a config entry.

    Closing the client and clearing the router issue are registered as
    on-unload callbacks in ``async_setup_entry``, so they also run when setup
    itself failed; Home Assistant invokes them once the platforms are gone.
    """
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: HabitronConfigEntry) -> None:
    """Reload the entry so a changed host is picked up by the normal setup."""
    await hass.config_entries.async_reload(entry.entry_id)


@callback
def _async_adopt_hub_identity(
    hass: HomeAssistant,
    entry: HabitronConfigEntry,
    coordinator: HbtnCoordinator,
) -> None:
    """Move the entry onto the hub's MAC, the one identity every path derives.

    This config flow only ever keys an entry by the MAC. An entry can still
    carry an older id, though: the custom (HACS) integration falls back to a
    serial or the host when the hub answers without a usable ``lan mac``, and
    such an entry keeps that id when it moves over. Now that the hub has given
    us its MAC, rewrite the entry -- from here on the plain unique-id check
    recognises it, whatever address it moves to, and no extra matcher is
    needed.
    """
    if not coordinator.has_mac_uid or entry.unique_id == coordinator.uid:
        return
    _LOGGER.debug(
        "Adopting hub identity for %s: %s -> %s",
        entry.title,
        entry.unique_id,
        coordinator.uid,
    )
    hass.config_entries.async_update_entry(entry, unique_id=coordinator.uid)


def _async_cleanup_stale_devices(
    hass: HomeAssistant,
    entry: HabitronConfigEntry,
    coordinator: HbtnCoordinator,
) -> None:
    """Remove device-registry entries whose Habitron module is gone.

    Run after the coordinator's setup has populated ``router.modules``. The
    hub device and the router device are kept; everything else identified
    by ``(DOMAIN, <some uid>)`` is removed if that uid is no longer in
    the router's current module list.
    """
    keep_uids: set[str] = {coordinator.uid, coordinator.router.uid}
    keep_uids.update(module.uid for module in coordinator.router.modules)

    dev_reg = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        # A device entry can carry several identifiers; it is only stale when
        # *none* of its Habitron uids is on the bus any more. Removing on the
        # first stale one would delete a live device -- the same rule
        # ``async_remove_config_entry_device`` applies above.
        habitron_uids = {uid for domain, uid in device.identifiers if domain == DOMAIN}
        if habitron_uids and habitron_uids.isdisjoint(keep_uids):
            dev_reg.async_remove_device(device.id)
