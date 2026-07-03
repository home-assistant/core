"""The Midea LAN integration."""

from midealocal.const import DeviceType, ProtocolVersion
from midealocal.devices import device_selector

from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_IP_ADDRESS,
    CONF_MODEL,
    CONF_NAME,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_TOKEN,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import CONF_KEY, CONF_SUBTYPE
from .entity import MideaLanConfigEntry

_PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: MideaLanConfigEntry) -> bool:
    """Set up Midea LAN from a config entry."""

    data = entry.data
    device_id: int = data[CONF_DEVICE_ID]

    device = await hass.async_add_executor_job(
        device_selector,
        data.get(CONF_NAME, f"{device_id}"),
        device_id,
        data.get(CONF_TYPE, DeviceType.AC),
        data[CONF_IP_ADDRESS],
        data[CONF_PORT],
        data.get(CONF_TOKEN, ""),
        data.get(CONF_KEY, ""),
        ProtocolVersion(data[CONF_PROTOCOL]),
        data[CONF_MODEL],
        data.get(CONF_SUBTYPE, 0),
        "",
    )
    if device is None:
        raise ConfigEntryError("Unable to initialize device")

    await hass.async_add_executor_job(device.open)
    entry.runtime_data = device

    async def _close_device() -> None:
        await hass.async_add_executor_job(device.close)

    entry.async_on_unload(_close_device)
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MideaLanConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
