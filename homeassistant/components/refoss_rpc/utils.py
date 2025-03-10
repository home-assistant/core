"""refoss helpers functions."""

from __future__ import annotations

from datetime import datetime, timedelta
from ipaddress import IPv6Address, ip_address
from typing import Any, cast

from aiorefoss.rpc_device import RpcDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.util.dt import utcnow

from .const import DOMAIN, INPUTS_EVENTS_TYPES, LOGGER, UPTIME_DEVIATION


@callback
def async_remove_refoss_entity(
    hass: HomeAssistant, domain: str, unique_id: str
) -> None:
    """Remove a refoss entity."""
    entity_reg = er.async_get(hass)
    entity_id = entity_reg.async_get_entity_id(domain, DOMAIN, unique_id)
    if entity_id:
        LOGGER.debug("Removing entity: %s", entity_id)
        entity_reg.async_remove(entity_id)


def get_device_uptime(uptime: float, last_uptime: datetime | None) -> datetime:
    """Return device uptime string, tolerate up to 5 seconds deviation."""
    delta_uptime = utcnow() - timedelta(seconds=uptime)

    if (
        not last_uptime
        or abs((delta_uptime - last_uptime).total_seconds()) > UPTIME_DEVIATION
    ):
        return delta_uptime

    return last_uptime


def get_refoss_channel_name(device: RpcDevice, key: str) -> str:
    """Get name based on device and channel name."""
    device_name = device.name
    entity_name: str | None = None
    if key in device.config:
        entity_name = device.config[key].get("name")

    if entity_name is None:
        channel = key.split(":")[0]
        channel_id = key.split(":")[-1]
        if key.startswith(("input:", "switch:")):
            return f"{device_name} {channel.title()} {channel_id}"
        return device_name

    return entity_name


def get_refoss_entity_name(
    device: RpcDevice, key: str, description: str | None = None
) -> str:
    """Naming for refoss entity."""
    channel_name = get_refoss_channel_name(device, key)

    if description:
        return f"{channel_name} {description.lower()}"

    return channel_name


def get_refoss_key_instances(keys_dict: dict[str, Any], key: str) -> list[str]:
    """Return list of key instances for  device from a dict."""
    if key in keys_dict:
        return [key]

    return [k for k in keys_dict if k.startswith(f"{key}:")]


def get_refoss_key_ids(keys_dict: dict[str, Any], key: str) -> list[int]:
    """Return list of key ids for  device from a dict."""
    return [int(k.split(":")[1]) for k in keys_dict if k.startswith(f"{key}:")]


def is_refoss_input_button(
    config: dict[str, Any], status: dict[str, Any], key: str
) -> bool:
    """Return true if input's type is set to button."""
    return cast(bool, config[key]["type"] == "button")


def get_input_triggers(device: RpcDevice) -> list[tuple[str, str]]:
    """Return list of input triggers for  device."""
    triggers = []

    key_ids = get_refoss_key_ids(device.config, "input")

    for id_ in key_ids:
        key = f"input:{id_}"
        if not is_refoss_input_button(device.config, device.status, key):
            continue

        for trigger_type in INPUTS_EVENTS_TYPES:
            subtype = f"button{id_}"
            triggers.append((trigger_type, subtype))

    return triggers


@callback
def update_device_fw_info(
    hass: HomeAssistant, refossdevice: RpcDevice, entry: ConfigEntry
) -> None:
    """Update the firmware version information in the device registry."""
    assert entry.unique_id

    dev_reg = dr.async_get(hass)
    if device := dev_reg.async_get_device(
        identifiers={(DOMAIN, entry.entry_id)},
        connections={(CONNECTION_NETWORK_MAC, dr.format_mac(entry.unique_id))},
    ):
        if device.sw_version == refossdevice.firmware_version:
            return

        LOGGER.debug("Updating device registry info for %s", entry.title)

        dev_reg.async_update_device(device.id, sw_version=refossdevice.firmware_version)


def is_refoss_wifi_stations_disabled(
    config: dict[str, Any], _status: dict[str, Any], key: str
) -> bool:
    """Return true if  all WiFi stations are disabled."""
    if (
        config[key]["sta_1"]["enable"] is False
        and config[key]["sta_2"]["enable"] is False
    ):
        return True

    return False


def get_host(host: str) -> str:
    """Get the device IP address."""
    try:
        ip_object = ip_address(host)
    except ValueError:
        # host contains hostname
        return host

    if isinstance(ip_object, IPv6Address):
        return f"[{host}]"

    return host
