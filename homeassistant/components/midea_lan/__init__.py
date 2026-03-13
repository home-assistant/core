"""The Midea LAN integration."""

from __future__ import annotations

from typing import cast

from midealocal.const import DeviceType, ProtocolVersion
from midealocal.device import MideaDevice
from midealocal.devices import device_selector

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CUSTOMIZE,
    CONF_DEVICE_ID,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_TOKEN,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_KEY, CONF_MODEL, CONF_SUBTYPE, DEVICES, DOMAIN

_PLATFORMS: list[Platform] = [Platform.CLIMATE]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Register update listener called for config entry updates."""
    await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS),
    )
    device_id: int = cast("int", entry.data.get(CONF_DEVICE_ID))
    customize = entry.options.get(CONF_CUSTOMIZE, "")
    ip_address = entry.options.get(CONF_IP_ADDRESS, "")
    dev: MideaDevice = hass.data[DOMAIN][DEVICES].get(device_id)
    if dev:
        dev.set_customize(customize)
        if ip_address is not None:
            dev.set_ip_address(ip_address)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Midea LAN component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Midea LAN from a config entry."""

    data = entry.data
    options = entry.options

    device_type: int = data.get(CONF_TYPE, DeviceType.AC)
    device_id: int = data[CONF_DEVICE_ID]
    name: str = data.get(CONF_NAME, f"{device_id}")
    token: str = data.get(CONF_TOKEN) or ""
    key: str = data.get(CONF_KEY) or ""
    ip_address: str = options.get(CONF_IP_ADDRESS, data.get(CONF_IP_ADDRESS))
    port: int = data[CONF_PORT]
    model: str = data[CONF_MODEL]
    subtype: int = data.get(CONF_SUBTYPE, 0)
    protocol: ProtocolVersion = ProtocolVersion(data[CONF_PROTOCOL])
    customize: str = options.get(CONF_CUSTOMIZE, "")
    if protocol == ProtocolVersion.V3 and (key == "" or token == ""):
        raise ConfigEntryError("For V3 devices, the key and token are required")
    device = await hass.async_add_import_executor_job(
        device_selector,
        name,
        device_id,
        device_type,
        ip_address,
        port,
        token,
        key,
        protocol,
        model,
        subtype,
        customize,
    )
    if device:
        device.open()
        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}
        if DEVICES not in hass.data[DOMAIN]:
            hass.data[DOMAIN][DEVICES] = {}
        hass.data[DOMAIN][DEVICES][device_id] = device
        entry.runtime_data = device

        await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

        entry.async_on_unload(entry.add_update_listener(update_listener))
        return True

    raise ConfigEntryNotReady("Unable to initialize device")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
