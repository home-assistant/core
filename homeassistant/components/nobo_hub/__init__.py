"""The Nobø Ecohub integration."""

import logging

from pynobo import nobo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_NAME,
    CONF_IP_ADDRESS,
    CONF_MAC,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_HARDWARE_VERSION,
    ATTR_SOFTWARE_VERSION,
    CONF_OVERRIDE_TYPE,
    CONF_SERIAL,
    DOMAIN,
    NOBO_MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.SELECT, Platform.SENSOR]

type NoboHubConfigEntry = ConfigEntry[nobo]


async def async_setup_entry(hass: HomeAssistant, entry: NoboHubConfigEntry) -> bool:
    """Set up Nobø Ecohub from a config entry."""

    serial = entry.data[CONF_SERIAL]
    stored_ip = entry.data[CONF_IP_ADDRESS]

    async def _connect(ip: str) -> nobo:
        hub = nobo(
            serial=serial,
            ip=ip,
            discover=False,
            synchronous=False,
            timezone=dt_util.get_default_time_zone(),
        )
        await hub.connect()
        return hub

    try:
        hub = await _connect(stored_ip)
    except OSError as err:
        # Stored IP may be stale - try UDP rediscovery to pick up a new
        # DHCP lease (or a hub that's been moved).
        discovered = await nobo.async_discover_hubs(serial=serial)
        if not discovered:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"serial": serial, "ip": stored_ip},
            ) from err
        new_ip, _ = next(iter(discovered))
        try:
            hub = await _connect(new_ip)
        except OSError as rediscover_err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"serial": serial, "ip": new_ip},
            ) from rediscover_err
        if new_ip != stored_ip:
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_IP_ADDRESS: new_ip}
            )

    async def _async_close(event):
        """Close the Nobø Ecohub socket connection when HA stops."""
        await hub.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_close)
    )

    def _log_connection_state(_hub: nobo, connected: bool) -> None:
        """Log hub connection-state transitions."""
        if connected:
            _LOGGER.info("Reconnected to Nobø Ecohub %s", serial)
        else:
            _LOGGER.info("Lost connection to Nobø Ecohub %s", serial)

    hub.register_connection_callback(_log_connection_state)
    entry.async_on_unload(
        lambda: hub.deregister_connection_callback(_log_connection_state)
    )
    entry.runtime_data = hub

    device_registry = dr.async_get(hass)
    connections: set[tuple[str, str]] = set()
    if mac := entry.data.get(CONF_MAC):
        connections.add((CONNECTION_NETWORK_MAC, mac))
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, hub.hub_serial)},
        connections=connections,
        serial_number=hub.hub_serial,
        name=hub.hub_info[ATTR_NAME],
        manufacturer=NOBO_MANUFACTURER,
        model="Nobø Ecohub",
        sw_version=hub.hub_info[ATTR_SOFTWARE_VERSION],
        hw_version=hub.hub_info[ATTR_HARDWARE_VERSION],
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def _cleanup_devices(_hub: nobo) -> None:
        """Remove devices for zones and components no longer on the hub."""
        if not hub.connected:
            # While disconnected pynobo may hold stale topology; only reconcile
            # against a live, fully-synced hub.
            return
        expected_identifiers = {(DOMAIN, hub.hub_serial)}
        expected_identifiers.update(
            (DOMAIN, f"{hub.hub_serial}:{zone_id}") for zone_id in hub.zones
        )
        expected_identifiers.update((DOMAIN, serial) for serial in hub.components)
        # Runs inside pynobo's update-callback dispatch: removing a device
        # deregisters its entities' callbacks mid-iteration, which can skip a
        # following callback. Safe because a pynobo message carries a single
        # topology change, so a removal never coincides with a surviving
        # entity's update in the same dispatch.
        for device in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
            if device.identifiers.isdisjoint(expected_identifiers):
                device_registry.async_update_device(
                    device.id, remove_config_entry_id=entry.entry_id
                )

    _cleanup_devices(hub)
    hub.register_callback(_cleanup_devices)
    entry.async_on_unload(lambda: hub.deregister_callback(_cleanup_devices))

    await hub.start()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NoboHubConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.stop()

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: NoboHubConfigEntry) -> bool:
    """Migrate old entry."""
    if entry.version == 1 and entry.minor_version < 2:
        # Lowercase override_type to match translation keys.
        new_options = dict(entry.options)
        if (override_type := new_options.get(CONF_OVERRIDE_TYPE)) is not None:
            new_options[CONF_OVERRIDE_TYPE] = override_type.lower()
        hass.config_entries.async_update_entry(
            entry, options=new_options, version=1, minor_version=2
        )

    if entry.version == 1 and entry.minor_version < 3:
        # auto_discovered no longer affects behaviour; rediscovery is now
        # the unconditional fallback on connection failure.
        new_data = dict(entry.data)
        new_data.pop("auto_discovered", None)
        hass.config_entries.async_update_entry(
            entry, data=new_data, version=1, minor_version=3
        )

    return True
