"""The Habitron integration."""

import logging

from habitron_client import HabitronError, HabitronTimeoutError

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .communicate import HbtnComm
from .const import DOMAIN
from .coordinator import HabitronConfigEntry, HbtnCoordinator
from .smart_hub import SmartHub

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_migrate_entry(hass: HomeAssistant, entry: HabitronConfigEntry) -> bool:
    """Migrate an old config entry.

    Version 1 stored the host under the integration-specific ``habitron_host``
    key; version 2 uses Home Assistant's shared ``CONF_HOST``. Version 3 exists
    because the custom (HACS) integration also numbers its entries 2: Home
    Assistant skips this function when the versions match, so a migrating
    installation would keep the unused credential below. Bumping past it makes
    the cleanup run once for every entry that predates core.
    """
    # Only versions below 3 reach this: Home Assistant returns early when they
    # match and refuses anything higher before calling us.
    data = {**entry.data}
    if entry.version == 1 and "habitron_host" in data:
        data[CONF_HOST] = data.pop("habitron_host")
    # ``websock_token`` belonged to the SmartController Touch/Assist push path,
    # which this integration does not implement; drop the credential rather
    # than keep storing it unused. ``update_interval`` predates the move to a
    # fixed ``SCAN_INTERVAL`` and has not been read since.
    data.pop("websock_token", None)
    data.pop("update_interval", None)
    hass.config_entries.async_update_entry(entry, data=data, version=3)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HabitronConfigEntry) -> bool:
    """Set up Habitron from a config entry."""
    comm = HbtnComm(hass, entry)
    coordinator = HbtnCoordinator(hass, entry, comm)
    entry.runtime_data = coordinator
    try:
        # First refresh runs the SmartHub setup (connect + build model + register
        # devices) via the coordinator, then the first bus poll.
        await coordinator.async_config_entry_first_refresh()
    except (TimeoutError, HabitronTimeoutError) as ex:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="connect_timeout",
        ) from ex
    except ConnectionRefusedError as ex:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="connect_refused",
            translation_placeholders={"error": str(ex)},
        ) from ex
    except (OSError, ConnectionError) as ex:
        # Network-level failures (DNS, socket errors, ...) are transient
        # and should let HA retry the entry. Programming errors such as
        # AttributeError/KeyError must propagate so they show up in the
        # logs instead of being masked as a retry loop.
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="connect_error",
            translation_placeholders={"error": str(ex)},
        ) from ex
    except HabitronError as ex:
        # The library raises its own HabitronError subclasses (protocol /
        # connection errors) rather than OSError for a flaky or rebooting hub
        # — e.g. a dropped connection or a truncated response during setup.
        # Treat them as transient so HA retries the entry with backoff instead
        # of failing setup permanently. (HabitronTimeoutError, a subclass, is
        # already handled above with its own translation key.)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="connect_error",
            translation_placeholders={"error": str(ex)},
        ) from ex

    # Past the connection: everything below is local bookkeeping, so it stays
    # outside the handlers above. An unexpected failure here is a defect and
    # must surface as one, not disappear into an indefinite setup retry.

    # Before the update listener exists: adopting rewrites the entry, and
    # ``async_update_entry`` fires the listeners -- which would schedule a
    # reload while this very setup is still running.
    _async_adopt_hub_identity(hass, entry, coordinator.smart_hub)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    _async_cleanup_stale_devices(hass, entry, coordinator.smart_hub)

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
    smhub = config_entry.runtime_data.smart_hub
    present_uids = {smhub.uid, smhub.router.uid}
    present_uids.update(module.uid for module in smhub.router.modules)
    return not any(
        identifier[0] == DOMAIN and identifier[1] in present_uids
        for identifier in device_entry.identifiers
    )


async def async_unload_entry(hass: HomeAssistant, entry: HabitronConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    entry.runtime_data.async_clear_router_issue()
    await entry.runtime_data.smart_hub.async_close()

    return True


async def update_listener(hass: HomeAssistant, entry: HabitronConfigEntry) -> None:
    """Reload the entry so a changed host is picked up by the normal setup."""
    await hass.config_entries.async_reload(entry.entry_id)


@callback
def _async_adopt_hub_identity(
    hass: HomeAssistant,
    entry: HabitronConfigEntry,
    smhub: SmartHub,
) -> None:
    """Move the entry onto the hub's MAC, the one identity every path derives.

    An entry can carry an older id: both the custom (HACS) integration and this
    config flow fall back to a serial or the host for a hub that answers but
    reports no usable ``lan mac``. Such a hub keeps that id for as long as the
    MAC stays unreadable; once it becomes readable we know the MAC here, so
    rewrite the entry -- from here on the plain unique-id check recognises it,
    whatever address it moves to, and no extra matcher is needed.
    """
    if not smhub.has_mac_uid or entry.unique_id == smhub.uid:
        return
    if hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, smhub.uid):
        # Another entry already owns this hub. Both would build their model from
        # the same MAC-derived uid, and entity unique ids are keyed per domain
        # and platform, so the second entry's entities collide with the first
        # one's instead of standing beside them. Stop here and name the entry to
        # remove rather than load a duplicate that cannot work.
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="duplicate_hub",
            translation_placeholders={"host": smhub.host, "uid": smhub.uid},
        )
    _LOGGER.debug(
        "Adopting hub identity for %s: %s -> %s",
        entry.title,
        entry.unique_id,
        smhub.uid,
    )
    hass.config_entries.async_update_entry(entry, unique_id=smhub.uid)


def _async_cleanup_stale_devices(
    hass: HomeAssistant,
    entry: HabitronConfigEntry,
    smhub: SmartHub,
) -> None:
    """Remove device-registry entries whose Habitron module is gone.

    Run after ``smhub.async_setup`` populates ``router.modules``. The
    hub device and the router device are kept; everything else identified
    by ``(DOMAIN, <some uid>)`` is removed if that uid is no longer in
    the router's current module list.
    """
    keep_uids: set[str] = {smhub.uid, smhub.router.uid}
    keep_uids.update(getattr(module, "uid", "") for module in smhub.router.modules)
    keep_uids.discard("")

    dev_reg = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        # A device entry can carry several identifiers; it is only stale when
        # *none* of its Habitron uids is on the bus any more. Removing on the
        # first stale one would delete a live device -- the same rule
        # ``async_remove_config_entry_device`` applies above.
        habitron_uids = {uid for domain, uid in device.identifiers if domain == DOMAIN}
        if habitron_uids and habitron_uids.isdisjoint(keep_uids):
            dev_reg.async_remove_device(device.id)
