"""Support for SolarEdge inverters over Modbus.

The inverter is a Modbus device. This integration does not own its connection:
it borrows a ``ModbusUnit`` from the ``modbus`` integration, which shares one
connection per device between everything talking to it, and hands that unit to
the ``solaredged`` library.
"""

from typing import TYPE_CHECKING

from solaredged import SolarEdge, SolarEdgeConnectionError, SolarEdgeError

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import device_registry as dr

from .const import CONF_UNIT_ID, DOMAIN
from .coordinator import (
    SolarEdgeModbusConfigEntry,
    SolarEdgeModbusDataUpdateCoordinator,
    SolarEdgeModbusRuntimeData,
)
from .entity import inverter_device_info
from .helpers import create_modbus_params

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: SolarEdgeModbusConfigEntry
) -> bool:
    """Set up SolarEdge Modbus from a config entry."""
    serial_number = entry.unique_id
    if TYPE_CHECKING:
        assert serial_number is not None

    try:
        unit = async_get_unit(
            hass, entry, create_modbus_params(entry.data), entry.data[CONF_UNIT_ID]
        )
    except HomeAssistantError as err:
        # The device is already in use over different link settings, which one
        # shared connection cannot honour.
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="link_settings_in_use",
            translation_placeholders={"error": str(err)},
        ) from err

    try:
        solaredge = await SolarEdge.async_probe(unit)
    except SolarEdgeConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="communication_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except SolarEdgeError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="no_solaredge_device",
        ) from err

    readings = SolarEdgeModbusDataUpdateCoordinator(hass, entry, solaredge)
    await readings.async_config_entry_first_refresh()

    # Identity arrives with that first read. An address or device ID can end up
    # pointing at another inverter (a reused DHCP lease, a changed setting), and
    # every identity here derives from the entry's serial, so stop rather than
    # hang this entry's name and history on a different device.
    probed = solaredge.common.serial_number
    if probed is not None and probed != serial_number:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="wrong_inverter",
        )

    inverter = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        **inverter_device_info(solaredge, serial_number),
    )
    entry.runtime_data = SolarEdgeModbusRuntimeData(
        readings=readings, inverter_device_id=inverter.id
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SolarEdgeModbusConfigEntry
) -> bool:
    """Unload SolarEdge Modbus config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
