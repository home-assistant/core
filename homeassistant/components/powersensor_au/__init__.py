"""The Powersensor integration."""

import logging

from powersensor_local import VirtualHousehold
from powersensor_local.zeroconf_devices import PowersensorZeroconfDevices

from homeassistant.components import zeroconf
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import CFG_ROLES, DOMAIN, ROLE_SOLAR, VHH_DEVICE_ID
from .models import PowersensorConfigEntry, PowersensorRuntimeData
from .powersensor_message_dispatcher import PowersensorMessageDispatcher

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: PowersensorConfigEntry) -> None:
    """Set up integration from a config entry."""
    with_solar = ROLE_SOLAR in entry.data[CFG_ROLES].values()
    vhh = VirtualHousehold(with_solar, logger=_LOGGER)
    zc_instance = await zeroconf.async_get_instance(hass)
    devices = PowersensorZeroconfDevices(
        zeroconf_instance=zc_instance,
        # device_found carries no role; the relayed now_relaying_for supplies it.
        relay_now_relaying_for=True,
        logger=_LOGGER,
    )
    dispatcher = PowersensorMessageDispatcher(hass, entry, vhh, devices)

    entry.runtime_data = PowersensorRuntimeData(
        vhh=vhh,
        dispatcher=dispatcher,
        devices=devices,
    )

    try:
        await devices.start(dispatcher.on_device_event)
    except (OSError, RuntimeError) as err:
        await devices.stop()
        raise ConfigEntryNotReady(f"Failed to start device discovery: {err}") from err

    # Platforms are forwarded only after discovery has started so that a
    # ConfigEntryNotReady above cannot leave a stale platform registered.
    # Anything discovered before sensor.py connects its listeners is seeded
    # from dispatcher.plugs / dispatcher.sensors when it loads.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: PowersensorConfigEntry
) -> None:
    """Unload a config entry."""
    # Stop events before unloading platforms: the platform's listeners are only
    # removed after this returns, so an event arriving while a platform resets
    # would add entities to it that are never removed.
    await entry.runtime_data.dispatcher.disconnect()
    await entry.runtime_data.devices.stop()
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: PowersensorConfigEntry,
    device_entry: dr.AnyDeviceEntry,
) -> bool:
    """Allow the user to delete a plug or sensor that has left the network.

    A device still on the network is refused: it would only come back with its
    next reading.  A plug or sensor counts as gone once it has been unplugged or
    switched off for a few minutes.

    The household view is never deleted.  It belongs to the installation as a
    whole rather than to one device, and a household that has genuinely changed
    is set up again by removing the integration and adding it again.

    A deleted sensor's saved role is deliberately kept in the config entry.
    The household view's with_solar flag is rebuilt from the saved roles at
    setup, and a solar sensor whose battery has run flat is one a user may well
    delete.  Dropping its role would make the household report home use without
    solar after the next restart, which is the incorrect data the one-way solar
    flag exists to prevent.  The role also serves as the fallback if the sensor
    returns.
    """
    dispatcher = config_entry.runtime_data.dispatcher
    ids = {id_ for domain, id_ in device_entry.identifiers if domain == DOMAIN}
    if VHH_DEVICE_ID in ids or any(dispatcher.is_present(mac) for mac in ids):
        return False
    for mac in ids:
        dispatcher.forget(mac)
    return True
