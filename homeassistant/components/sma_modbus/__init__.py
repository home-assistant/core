"""The SMA Modbus integration.

This integration reads Modbus TCP registers from SMA energy devices
(Sunny Boy, Sunny Boy Smart Energy, Sunny Tripower, Sunny Home Manager).

Communication is handled by the ``sma-modbus`` library which models each
device as a ``modbus_connection`` Component with typed register fields.

The integration does not own its Modbus connection: it borrows a
``ModbusUnit`` from the ``modbus`` integration and wraps it so the
sma-modbus library can use it like a ``ModbusConnection``.
"""

import logging

from modbus_connection import ModbusError, ModbusTcpParams
from sma_modbus import DEVICE_CLASSES, DeviceType, SmaComponent, discover

from homeassistant.components.modbus import async_get_unit
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)

from .connection import ModbusUnitConnection
from .const import CONF_DEVICE_TYPE, CONF_UNIT_ID, DEFAULT_PORT, DOMAIN
from .coordinator import SmaCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type SmaConfigEntry = ConfigEntry[SmaCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SmaConfigEntry) -> bool:
    """Set up SMA Modbus from a config entry."""
    host: str = entry.data[CONF_HOST]
    port: int = entry.data.get(CONF_PORT, DEFAULT_PORT)
    device_type = DeviceType(entry.data[CONF_DEVICE_TYPE])
    unit_id: int = (
        entry.data.get(CONF_UNIT_ID) or DEVICE_CLASSES[device_type].default_unit_id
    )

    params = ModbusTcpParams(host=host, port=port)

    try:
        unit = async_get_unit(hass, entry, params, unit_id)
    except HomeAssistantError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err

    adapter = ModbusUnitConnection(unit)

    try:
        info = await discover(adapter, unit_id=unit_id)
    except ModbusError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err

    if f"SMA{info.serial_number}" != entry.unique_id:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="wrong_device",
        )

    device: SmaComponent = DEVICE_CLASSES[device_type](adapter, info.unit_id)

    coordinator = SmaCoordinator(hass, entry, device, device_type)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SmaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
