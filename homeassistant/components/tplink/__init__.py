"""Component to embed TP-Link smart home devices."""
from __future__ import annotations

from typing import Any

from kasa import SmartDevice, SmartDeviceException
from kasa.discover import Discover
from kasa.protocol import TPLinkSmartHomeProtocol
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_DIMMER,
    CONF_DISCOVERY,
    CONF_LEGACY_ENTRY_ID,
    CONF_LIGHT,
    CONF_STRIP,
    CONF_SWITCH,
    DISCOVERED_DEVICES,
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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the TP-Link component."""
    conf = config.get(DOMAIN)
    hass.data[DOMAIN] = {}

    legacy_entry = None
    config_entries_by_mac = {}
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.unique_id is None or entry.unique_id == DOMAIN:
            legacy_entry = entry
        else:
            config_entries_by_mac[entry.unique_id] = entry

    discovered_devices = {
        dr.format_mac(device.mac): device
        for device in (await Discover.discover()).values()
    }
    hass.data[DOMAIN][DISCOVERED_DEVICES] = discovered_devices

    if legacy_entry:
        async_migrate_legacy_entries(hass, config_entries_by_mac, legacy_entry)

    if conf is not None:
        async_migrate_yaml_entries(hass, conf)

    if discovered_devices:
        async_trigger_discovery(hass, discovered_devices)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TPLink from a config entry."""
    if not entry.unique_id or entry.unique_id == DOMAIN:
        return True

    if legacy_entry_id := entry.data.get(CONF_LEGACY_ENTRY_ID):
        await async_migrate_entities_devices(hass, legacy_entry_id, entry)

    protocol = TPLinkSmartHomeProtocol(entry.data[CONF_HOST])
    try:
        info = await protocol.query(Discover.DISCOVERY_QUERY)
    except SmartDeviceException as ex:
        raise ConfigEntryNotReady from ex

    device_class = Discover._get_device_class(info)  # pylint: disable=protected-access
    device = device_class(entry.data[CONF_HOST])
    coordinator = TPLinkDataUpdateCoordinator(hass, device)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass_data: dict[str, Any] = hass.data[DOMAIN]
    if entry.entry_id not in hass_data:
        return True
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass_data.pop(entry.entry_id)
    return unload_ok
