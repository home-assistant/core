"""The Midea LAN integration."""

from __future__ import annotations

from typing import cast

from midealocal.const import ProtocolVersion
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
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    _LOGGER,
    CONF_KEY,
    CONF_MODEL,
    CONF_REFRESH_INTERVAL,
    CONF_SUBTYPE,
    DEVICES,
    DOMAIN,
    EXTRA_SWITCH,
)
from .devices import MIDEA_DEVICES

_PLATFORMS: list[Platform] = [Platform.CLIMATE]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Register update listener called for config entry updates."""
    # Forward the unloading of an entry to platforms.
    await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    # forward the Config Entry to the platforms
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS),
    )
    device_id: int = cast("int", entry.data.get(CONF_DEVICE_ID))
    customize = entry.options.get(CONF_CUSTOMIZE, "")
    ip_address = entry.options.get(CONF_IP_ADDRESS, "")
    refresh_interval = entry.options.get(CONF_REFRESH_INTERVAL, None)
    dev: MideaDevice = hass.data[DOMAIN][DEVICES].get(device_id)
    if dev:
        dev.set_customize(customize)
        if ip_address is not None:
            dev.set_ip_address(ip_address)
        if refresh_interval is not None:
            dev.set_refresh_interval(refresh_interval)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Midea LAN component."""
    hass.data.setdefault(DOMAIN, {})
    attributes = []
    for device_entities in MIDEA_DEVICES.values():
        for attribute_name, attribute in cast(
            "dict",
            device_entities["entities"],
        ).items():
            if (
                attribute.get("type") in EXTRA_SWITCH
                and attribute_name.value not in attributes
            ):
                attributes.append(attribute_name.value)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Midea LAN from a config entry."""

    data = entry.runtime_data

    device_type: int = data.get(CONF_TYPE, 0xAC)
    device_id: int = data[CONF_DEVICE_ID]
    name: str = data.get(CONF_NAME, f"{device_id}")
    token: str = data.get(CONF_TOKEN) or ""
    key: str = data.get(CONF_KEY) or ""
    ip_address: str = data.options.get(CONF_IP_ADDRESS, data.get(CONF_IP_ADDRESS))
    refresh_interval: int | None = data.options.get(CONF_REFRESH_INTERVAL)
    port: int = data[CONF_PORT]
    model: str = data[CONF_MODEL]
    subtype: int = data.get(CONF_SUBTYPE, 0)
    protocol: ProtocolVersion = ProtocolVersion(data[CONF_PROTOCOL])
    customize: str = data.options.get(CONF_CUSTOMIZE, "")
    if protocol == ProtocolVersion.V3 and (key == "" or token == ""):
        _LOGGER.error("For V3 devices, the key and the token is required")
        return False
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
        if refresh_interval is not None:
            device.set_refresh_interval(refresh_interval)
        device.open()
        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}
        if DEVICES not in hass.data[DOMAIN]:
            hass.data[DOMAIN][DEVICES] = {}
        hass.data[DOMAIN][DEVICES][device_id] = device
        # Forward the setup of an entry to all platforms
        await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
        # Listener `update_listener` is
        # attached when the entry is loaded
        # and detached when it's unloaded
        entry.async_on_unload(entry.add_update_listener(update_listener))
        return True

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
