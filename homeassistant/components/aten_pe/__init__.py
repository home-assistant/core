"""The ATEN PE component."""

from dataclasses import dataclass
import logging

from atenpdu import AtenPE, AtenPEError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo

from .const import (
    CAP_PERPORTREADING,
    CAP_SWITCHABLE,
    CONF_AUTH_KEY,
    CONF_COMMUNITY,
    CONF_PRIV_KEY,
)
from .util import create_aten_pe_device

PLATFORMS = [Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)


@dataclass
class AtenPEData:
    """Runtime data for the ATEN PE integration."""

    device: AtenPE
    device_info: DeviceInfo
    mac: str
    switchable: bool
    perportreading: bool


type AtenPEConfigEntry = ConfigEntry[AtenPEData]


async def async_setup_entry(hass: HomeAssistant, entry: AtenPEConfigEntry) -> bool:
    """Set up a config entry."""
    config = entry.data

    node = config[CONF_HOST]
    serv = config[CONF_PORT]

    dev = await hass.async_add_executor_job(
        create_aten_pe_device,
        node,
        serv,
        config[CONF_COMMUNITY],
        config[CONF_USERNAME],
        config.get(CONF_AUTH_KEY),
        config.get(CONF_PRIV_KEY),
    )

    try:
        await dev.initialize()
        mac = await dev.deviceMAC()
        name = await dev.deviceName()
        model = await dev.modelName()
        sw_version = await dev.deviceFWversion()
        switchable_raw = await dev.getAttribute(CAP_SWITCHABLE)
        perportreading_raw = await dev.getAttribute(CAP_PERPORTREADING)
    except AtenPEError as exc:
        _LOGGER.error("Failed to initialize %s:%s: %s", node, serv, str(exc))
        dev.close()
        raise ConfigEntryNotReady from exc

    def _resolve(val):
        return str(val.getNamedValues().getName(val))

    switchable = _resolve(switchable_raw) in ("yes", "mix")
    perportreading = _resolve(perportreading_raw) == "yes"

    info = DeviceInfo(
        connections={(CONNECTION_NETWORK_MAC, mac)},
        manufacturer="ATEN",
        model=model,
        name=name,
        sw_version=sw_version,
    )

    entry.runtime_data = AtenPEData(
        device=dev,
        device_info=info,
        mac=mac,
        switchable=switchable,
        perportreading=perportreading,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AtenPEConfigEntry) -> bool:
    """Unload a config entry."""
    data = entry.runtime_data
    data.device.close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
