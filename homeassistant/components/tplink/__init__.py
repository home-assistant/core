"""Component to embed TP-Link smart home devices."""
from __future__ import annotations

import asyncio
from typing import Any

from kasa import SmartDevice, SmartDeviceException
from kasa.discover import Discover
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_DIMMER,
    CONF_DISCOVERY,
    CONF_LIGHT,
    CONF_STRIP,
    CONF_SWITCH,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import TPLinkDataUpdateCoordinator
from .migration import (
    async_migrate_entities_devices,
    async_migrate_legacy_entries,
    async_migrate_yaml_entries,
)

TPLINK_HOST_SCHEMA = vol.Schema({vol.Required(CONF_HOST): cv.string})

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Optional(CONF_LIGHT, default=[]): vol.All(
                        cv.ensure_list, [TPLINK_HOST_SCHEMA]
                    ),
                    vol.Optional(CONF_SWITCH, default=[]): vol.All(
                        cv.ensure_list, [TPLINK_HOST_SCHEMA]
                    ),
                    vol.Optional(CONF_STRIP, default=[]): vol.All(
                        cv.ensure_list, [TPLINK_HOST_SCHEMA]
                    ),
                    vol.Optional(CONF_DIMMER, default=[]): vol.All(
                        cv.ensure_list, [TPLINK_HOST_SCHEMA]
                    ),
                    vol.Optional(CONF_DISCOVERY, default=True): cv.boolean,
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


@callback
def async_trigger_discovery(
    hass: HomeAssistant,
    discovered_devices: dict[str, SmartDevice],
) -> None:
    """Trigger config flows for discovered devices."""
    for formatted_mac, device in discovered_devices.items():
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_DISCOVERY},
                data={
                    CONF_NAME: device.alias,
                    CONF_HOST: device.host,
                    CONF_MAC: formatted_mac,
                },
            )
        )


async def async_discover_devices(hass: HomeAssistant) -> dict[str, SmartDevice]:
    """Discover TPLink devices on configured network interfaces."""
    broadcast_addresses = await network.async_get_ipv4_broadcast_addresses(hass)
    tasks = [Discover.discover(target=str(address)) for address in broadcast_addresses]
    discovered_devices: dict[str, SmartDevice] = {}
    for device_list in await asyncio.gather(*tasks):
        for device in device_list.values():
            discovered_devices[dr.format_mac(device.mac)] = device
    return discovered_devices


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the TP-Link component."""
    conf = config.get(DOMAIN)
    hass.data[DOMAIN] = {}
    legacy_entry = None
    config_entries_by_mac = {}
    for entry in hass.config_entries.async_entries(DOMAIN):
        if async_entry_is_legacy(entry):
            legacy_entry = entry
        elif entry.unique_id:
            config_entries_by_mac[entry.unique_id] = entry

    discovered_devices = await async_discover_devices(hass)
    hosts_by_mac = {mac: device.host for mac, device in discovered_devices.items()}

    if legacy_entry:
        async_migrate_legacy_entries(
            hass, hosts_by_mac, config_entries_by_mac, legacy_entry
        )

    if conf is not None:
        async_migrate_yaml_entries(hass, conf)

    if discovered_devices:
        async_trigger_discovery(hass, discovered_devices)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TPLink from a config entry."""
    if async_entry_is_legacy(entry):
        return True

    legacy_entry: ConfigEntry | None = None
    for config_entry in hass.config_entries.async_entries(DOMAIN):
        if async_entry_is_legacy(config_entry):
            legacy_entry = config_entry
            break

    if legacy_entry is not None:
        await async_migrate_entities_devices(hass, legacy_entry.entry_id, entry)

    try:
        device: SmartDevice = await Discover.discover_single(entry.data[CONF_HOST])
    except SmartDeviceException as ex:
        raise ConfigEntryNotReady from ex

    hass.data[DOMAIN][entry.entry_id] = TPLinkDataUpdateCoordinator(hass, device)
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass_data: dict[str, Any] = hass.data[DOMAIN]
    if entry.entry_id not in hass_data:
        return True
    device: SmartDevice = hass.data[DOMAIN][entry.entry_id].device
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass_data.pop(entry.entry_id)
    await device.protocol.close()
    return unload_ok


@callback
def async_entry_is_legacy(entry: ConfigEntry) -> bool:
    """Check if a config entry is the legacy shared one."""
    return entry.unique_id is None or entry.unique_id == DOMAIN


def legacy_device_id(device: SmartDevice) -> str:
    """Convert the device id so it matches what was used in the original version."""
    device_id: str = device.device_id
    # Plugs are prefixed with the mac in python-kasa but not
    # in pyHS100 so we need to strip off the mac
    if "_" not in device_id:
        return device_id
    return device_id.split("_")[1]
