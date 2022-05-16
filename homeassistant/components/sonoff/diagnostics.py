from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .core.const import DOMAIN, PRIVATE_KEYS, source_hash
from .core.ewelink import XRegistry


async def async_get_config_entry_diagnostics(
        hass: HomeAssistant, entry: ConfigEntry
):
    try:
        if XRegistry.config:
            config = XRegistry.config.copy()
            for k in (CONF_USERNAME, CONF_PASSWORD):
                if config.get(k):
                    config[k] = "***"
            if config.get("devices"):
                for device in config["devices"].values():
                    if device.get("devicekey"):
                        device["devicekey"] = "***"
        else:
            config = None
    except Exception as e:
        config = f"{type(e).__name__}: {e}"

    options = {
        k: len(v) if k == "homes" else v for k, v in entry.options.items()
    }

    registry: XRegistry = hass.data[DOMAIN][entry.entry_id]
    try:
        devices = {
            did: {
                "uiid": device["extra"]["uiid"],
                "params": {
                    k: "***" if k in PRIVATE_KEYS else v
                    for k, v in device["params"].items()
                },
                "model": device.get("productModel"),
                "online": device.get("online"),
                "localtype": device.get("localtype"),
            } if "params" in device else {
                "localtype": device.get("localtype"),
            } for did, device in registry.devices.items()
        }
    except Exception as e:
        devices = f"{type(e).__name__}: {e}"

    try:
        errors = [
            entry.to_dict()
            for key, entry in hass.data["system_log"].records.items()
            if DOMAIN in key
        ]
    except Exception as e:
        errors = f"{type(e).__name__}: {e}"

    return {
        "version": source_hash(),
        "cloud_auth": registry.cloud.auth is not None,
        "config": config,
        "options": options,
        "errors": errors,
        "devices": devices,
    }


async def async_get_device_diagnostics(
        hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
):
    did = next(i[1] for i in device.identifiers if i[0] == DOMAIN)
    info = await async_get_config_entry_diagnostics(hass, entry)
    info["device"] = info.pop("devices")[did]
    info["device"]["deviceid"] = did
    return info
