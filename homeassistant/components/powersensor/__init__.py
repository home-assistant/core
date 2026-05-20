"""The Powersensor integration.

Powersensor is a hub-based energy monitoring system.  One or more Powersensor
gateways (smart plugs) are discovered automatically via zeroconf
(``_powersensor._udp.local.``).  Each gateway relays push messages from paired
wireless magnetic sensors and water sensors over UDP to this integration.

A single config entry covers the whole household.  The integration creates:

- A ``PowersensorDiscoveryService`` that listens for gateways on the local
  network and fires dispatcher signals as they appear or disappear.
- A ``PowersensorMessageDispatcher`` (coordinator) that manages the lifecycle
  of connected plug APIs, queues them for setup, and routes incoming push
  messages to per-entity dispatcher signals.
- A ``VirtualHousehold`` (from the ``powersensor_local`` library) that
  aggregates mains and solar magnetic readings into whole-home power and energy
  figures.

Because devices push data rather than being polled, the integration uses
``iot_class: local_push`` and does not use ``DataUpdateCoordinator``.
"""

import logging

from powersensor_local import VirtualHousehold
from zeroconf import BadTypeInNameException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError

from .config_flow import PowersensorConfigFlow
from .const import CFG_DEVICES, CFG_ROLES, ROLE_SOLAR, ZEROCONF_SERVICE_TYPE
from .models import PowersensorConfigEntry, PowersensorRuntimeData
from .powersensor_discovery_service import PowersensorDiscoveryService
from .powersensor_message_dispatcher import PowersensorMessageDispatcher

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

#
# config entry.data structure (version 2.2):
#   {
#     devices = {
#       mac = {
#         name =,
#         display_name =,
#         mac =,
#         host =,
#         port =,
#     }
#     roles = {
#       mac = role,
#     }
#   }
#


async def async_setup_entry(hass: HomeAssistant, entry: PowersensorConfigEntry) -> bool:
    """Set up integration from a config entry."""
    zeroconf_service = PowersensorDiscoveryService(hass, ZEROCONF_SERVICE_TYPE)
    try:
        with_solar = ROLE_SOLAR in entry.data.get(CFG_ROLES, {}).values()
        vhh = VirtualHousehold(with_solar)

        dispatcher = PowersensorMessageDispatcher(hass, entry, vhh)
        for device in entry.data.get(CFG_DEVICES, {}).values():
            dispatcher.enqueue_plug_for_adding(
                device["mac"], device["host"], device["port"], device["name"]
            )
    except (KeyError, ValueError, HomeAssistantError) as err:
        raise ConfigEntryNotReady(f"Unexpected error during setup: {err}") from err

    entry.runtime_data = PowersensorRuntimeData(
        vhh=vhh,
        dispatcher=dispatcher,
        zeroconf=zeroconf_service,
        with_solar=with_solar,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # async_forward_entry_setups does not return until sensor.py's
    # async_setup_entry has completed, so CREATE_PLUG_SIGNAL listeners are
    # registered and ready.  Process the queue now rather than relying on a
    # timed poll.
    dispatcher.process_plug_queue()

    # Start the discovery service only after the initial queue has been drained
    # and _known_plugs is fully populated.  Starting earlier allows zeroconf
    # update_service callbacks to race process_plug_queue: _plug_updated sees
    # empty _known_plugs, enqueues plugs, drains the queue before
    # CREATE_PLUG_SIGNAL listeners are registered (firing signals into the
    # void), and leaves all previously-known plugs stranded on restart.
    try:
        await zeroconf_service.start()
    except (
        BadTypeInNameException,
        OSError,
        NotImplementedError,
        HomeAssistantError,
        RuntimeError,
    ) as err:
        await zeroconf_service.stop()
        raise ConfigEntryNotReady(f"Failed to start discovery service: {err}") from err

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: PowersensorConfigEntry
) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Started unloading for %s", entry.entry_id)
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        runtime = entry.runtime_data
        await runtime.dispatcher.disconnect()
        await runtime.zeroconf.stop()
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entry."""
    _LOGGER.debug("Upgrading config from %s.%s", entry.version, entry.minor_version)
    if entry.version > PowersensorConfigFlow.VERSION:
        return False

    # Migration steps are applied in order so that a user skipping multiple
    # versions is brought all the way up to current in a single pass.
    if entry.version == 1:
        # v1 → v2: flat device dict moved under CFG_DEVICES; CFG_ROLES added.
        devices = {**entry.data}
        new_data = {CFG_DEVICES: devices, CFG_ROLES: {}}
        hass.config_entries.async_update_entry(
            entry, data=new_data, version=2, minor_version=2
        )

    # Future migration steps go here, e.g.:
    # if entry.version == 2 and entry.minor_version < 3:
    #     ...

    _LOGGER.debug("Upgrading config to %s.%s", entry.version, entry.minor_version)
    return True
