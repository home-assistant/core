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
    with_solar = ROLE_SOLAR in entry.data.get(CFG_ROLES, {}).values()
    vhh = VirtualHousehold(with_solar)
    dispatcher = PowersensorMessageDispatcher(hass, entry, vhh)
    zc_instance = await zeroconf.async_get_instance(hass)
    devices = PowersensorZeroconfDevices(
        zeroconf_instance=zc_instance,
        relay_now_relaying_for=True,
        logger=_LOGGER,
    )

    entry.runtime_data = PowersensorRuntimeData(
        vhh=vhh,
        dispatcher=dispatcher,
        devices=devices,
    )

    # Register platform signal listeners before starting discovery so that
    # device_found events fired during devices.start() land on ready listeners.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start the mDNS service browser.  Unlike the legacy UDP scan, start() is
    # non-blocking — it registers a ServiceBrowser and returns immediately.
    # Plugs already on the network will fire add_service callbacks shortly
    # after; there is no scan_complete event to wait for.
    try:
        await devices.start(dispatcher.on_device_event)
    except (OSError, RuntimeError) as err:
        await devices.stop()
        raise ConfigEntryNotReady(f"Failed to start device discovery: {err}") from err

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: PowersensorConfigEntry
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.dispatcher.disconnect()
        await entry.runtime_data.devices.stop()
    return unload_ok
