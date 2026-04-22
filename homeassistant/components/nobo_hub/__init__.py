"""The Nobø Ecohub integration."""

from __future__ import annotations

from pynobo import nobo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_NAME,
    CONF_IP_ADDRESS,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_HARDWARE_VERSION,
    ATTR_SOFTWARE_VERSION,
    CONF_AUTO_DISCOVERED,
    CONF_OVERRIDE_TYPE,
    CONF_SERIAL,
    DOMAIN,
    NOBO_MANUFACTURER,
)

PLATFORMS = [Platform.CLIMATE, Platform.SELECT, Platform.SENSOR]

type NoboHubConfigEntry = ConfigEntry[nobo]


async def async_setup_entry(hass: HomeAssistant, entry: NoboHubConfigEntry) -> bool:
    """Set up Nobø Ecohub from a config entry."""

    serial = entry.data[CONF_SERIAL]
    stored_ip = entry.data[CONF_IP_ADDRESS]
    auto_discovered = entry.data[CONF_AUTO_DISCOVERED]

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
        if not auto_discovered:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect_manual",
                translation_placeholders={"serial": serial, "ip": stored_ip},
            ) from err
        # Stored IP may be stale for an auto-discovered entry - try UDP
        # rediscovery to pick up a new DHCP lease.
        discovered = await nobo.async_discover_hubs(serial=serial)
        if not discovered:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="hub_not_found",
                translation_placeholders={"serial": serial},
            ) from err
        new_ip, _ = next(iter(discovered))
        try:
            hub = await _connect(new_ip)
        except OSError as rediscover_err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect_rediscovered",
                translation_placeholders={"ip": new_ip},
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
    entry.runtime_data = hub

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, hub.hub_serial)},
        serial_number=hub.hub_serial,
        name=hub.hub_info[ATTR_NAME],
        manufacturer=NOBO_MANUFACTURER,
        model="Nobø Ecohub",
        sw_version=hub.hub_info[ATTR_SOFTWARE_VERSION],
        hw_version=hub.hub_info[ATTR_HARDWARE_VERSION],
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

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

    return True
