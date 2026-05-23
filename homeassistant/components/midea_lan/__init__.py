"""The Midea LAN integration."""

from midealocal.const import DeviceType, ProtocolVersion
from midealocal.devices import device_selector

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
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

from .const import CONF_KEY, CONF_MODEL, CONF_SUBTYPE, DOMAIN

_PLATFORMS: list[Platform] = [Platform.CLIMATE]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Midea LAN component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Midea LAN from a config entry."""

    data = entry.data

    device_type: int = data.get(CONF_TYPE, DeviceType.AC)
    device_id: int = data[CONF_DEVICE_ID]
    name: str = data.get(CONF_NAME, f"{device_id}")
    token: str = data.get(CONF_TOKEN, "")
    key: str = data.get(CONF_KEY, "")
    ip_address: str = data[CONF_IP_ADDRESS]
    port: int = data[CONF_PORT]
    model: str = data[CONF_MODEL]
    subtype: int = data.get(CONF_SUBTYPE, 0)
    protocol: ProtocolVersion = ProtocolVersion(data[CONF_PROTOCOL])
    if protocol == ProtocolVersion.V3 and (key == "" or token == ""):
        raise ConfigEntryError("For V3 devices, the key and token are required")
    device = await hass.async_add_executor_job(
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
        "",
    )
    if device:
        await hass.async_add_executor_job(device.open)
        entry.runtime_data = device

        async def _close_device() -> None:
            await hass.async_add_executor_job(device.close)

        entry.async_on_unload(_close_device)
        await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
        return True

    raise ConfigEntryNotReady("Unable to initialize device")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
