"""The Powersensor integration."""

import logging

from powersensor_local import VirtualHousehold
from powersensor_local.zeroconf_devices import PowersensorZeroconfDevices

from homeassistant.components import zeroconf
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CFG_ROLES, ROLE_SOLAR
from .models import PowersensorConfigEntry, PowersensorRuntimeData
from .powersensor_message_dispatcher import PowersensorMessageDispatcher

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: PowersensorConfigEntry) -> bool:
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

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: PowersensorConfigEntry
) -> bool:
    """Unload a config entry."""
    # Stop events before unloading platforms: the platform's listeners are only
    # removed after this returns, so an event arriving while a platform resets
    # would add entities to it that are never removed.
    await entry.runtime_data.dispatcher.disconnect()
    await entry.runtime_data.devices.stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
