"""The Huawei Solar integration."""
from __future__ import annotations

from huawei_solar import AsyncHuaweiSolar, HuaweiSolarException, register_names as rn

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    CONF_SLAVE_IDS,
    DATA_DEVICE_INFO,
    DATA_EXTRA_SLAVE_IDS,
    DATA_MODBUS_CLIENT,
    DOMAIN,
)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Huawei Solar from a config entry."""

    try:
        inverter = await AsyncHuaweiSolar.create(
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            slave=entry.data[CONF_SLAVE_IDS][0],
        )

        model_name, serial_number = await inverter.get_multiple(
            [rn.MODEL_NAME, rn.SERIAL_NUMBER]
        )
    except HuaweiSolarException as err:
        raise ConfigEntryNotReady from err

    device_info = DeviceInfo(
        identifiers={(DOMAIN, str(model_name.value), str(serial_number.value))},  # type: ignore
        name=model_name.value,
        manufacturer="Huawei",
        model=model_name.value,
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_MODBUS_CLIENT: inverter,
        DATA_DEVICE_INFO: device_info,
        DATA_EXTRA_SLAVE_IDS: entry.data[CONF_SLAVE_IDS][1:],
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        client = hass.data[DOMAIN][entry.entry_id][DATA_MODBUS_CLIENT]
        await client.stop()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
