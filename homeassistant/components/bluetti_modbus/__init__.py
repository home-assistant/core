"""Support for BLUETTI power stations over Modbus.

The device is a Modbus device like any other: this integration does not own
its connection, it borrows a ``ModbusUnit`` from the ``modbus`` integration,
which shares one connection per device between everything talking to it, and
hands that unit to the ``bluetti-modbus`` library.
"""

from bluetti_modbus_lib.devices.getter import get_device
from modbus_connection import ModbusTcpParams

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import CONF_DEVICE_TYPE, CONF_UNIT_ID, DOMAIN
from .coordinator import (
    BluettiModbusConfigEntry,
    BluettiModbusDataUpdateCoordinator,
    BluettiModbusRuntimeData,
)
from .entity import bluetti_modbus_device_info

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: BluettiModbusConfigEntry
) -> bool:
    """Set up BLUETTI Modbus from a config entry."""
    params = ModbusTcpParams(host=entry.data[CONF_HOST], port=entry.data[CONF_PORT])
    try:
        unit = async_get_unit(hass, entry, params, entry.data[CONF_UNIT_ID])
    except HomeAssistantError as err:
        # The device is already in use over different link settings, which
        # one shared connection cannot honour.
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="link_settings_in_use",
            translation_placeholders={"error": str(err)},
        ) from err

    device_type = entry.data[CONF_DEVICE_TYPE]
    device = get_device(device_type, unit)
    if device is None:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="unsupported_device_type",
        )

    coordinator = BluettiModbusDataUpdateCoordinator(hass, entry, device)
    await coordinator.async_config_entry_first_refresh()

    # Built once here: every entity hangs on the same device.
    entry.runtime_data = BluettiModbusRuntimeData(
        coordinator=coordinator,
        device_info=bluetti_modbus_device_info(entry.entry_id, device_type),
    )
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **entry.runtime_data.device_info
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: BluettiModbusConfigEntry
) -> bool:
    """Unload a BLUETTI Modbus config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
