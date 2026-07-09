"""The Habitron integration."""

from habitron_client import HabitronError, HabitronTimeoutError

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry

from .communicate import HbtnComm
from .const import DOMAIN
from .coordinator import HabitronConfigEntry, HbtnCoordinator
from .smart_hub import SmartHub

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: HabitronConfigEntry) -> bool:
    """Set up Habitron from a config entry."""
    comm = HbtnComm(hass, entry)
    coordinator = HbtnCoordinator(hass, entry, comm)
    entry.runtime_data = coordinator
    try:
        # First refresh runs the SmartHub setup (connect + build model + register
        # devices) via the coordinator, then the first bus poll.
        await coordinator.async_config_entry_first_refresh()

        entry.async_on_unload(entry.add_update_listener(update_listener))

        _async_cleanup_stale_devices(hass, entry, coordinator.smart_hub)

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

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
    else:
        return True


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: HabitronConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Remove a config entry from a device."""
    smhub = config_entry.runtime_data.smart_hub
    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN and identifier[1] == smhub.uid
    )


async def async_unload_entry(hass: HomeAssistant, entry: HabitronConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    await entry.runtime_data.smart_hub.async_close()

    return True


async def update_listener(hass: HomeAssistant, entry: HabitronConfigEntry) -> None:
    """Handle options update by reloading the config entry."""
    # Reload unconditionally so host, interval and token changes are picked up
    # via the normal setup path.
    await hass.config_entries.async_reload(entry.entry_id)


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
        for identifier in device.identifiers:
            if identifier[0] == DOMAIN and identifier[1] not in keep_uids:
                dev_reg.async_remove_device(device.id)
                break
