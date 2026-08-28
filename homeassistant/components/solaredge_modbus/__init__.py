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

from .const import CONF_UNIT_ID, DOMAIN, SUBSYSTEM_COMMON, SUBSYSTEM_INVERTER
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

    # Identity arrives with that first read, and a poll can come back without
    # it. Nothing can be checked then, so try again rather than accept the
    # entry: an address or device ID can end up pointing at another inverter (a
    # reused DHCP lease, a changed setting), and every identity here derives
    # from the entry's serial number.
    if SUBSYSTEM_COMMON in readings.data.failed:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="identity_unavailable",
        )

    # The platforms read the inverter's DID once, so without it the phase
    # entities would stay missing until a reload.
    if SUBSYSTEM_INVERTER in readings.data.failed:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="measurements_unavailable",
        )

    # Registered up front: a meter sub-device can only name the inverter it
    # hangs off once that device has an ID.
    device_info = inverter_device_info(solaredge, serial_number)
    inverter = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **device_info
    )
    entry.runtime_data = SolarEdgeModbusRuntimeData(
        readings=readings, device_info=device_info, inverter_device_id=inverter.id
    )

    _async_remove_stale_devices(hass, entry, solaredge, serial_number)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def _async_remove_stale_devices(
    hass: HomeAssistant,
    entry: SolarEdgeModbusConfigEntry,
    solaredge: SolarEdge,
    serial_number: str,
) -> None:
    """Remove devices for meters no longer attached to the inverter."""
    current = {(DOMAIN, serial_number)}
    current.update(
        (DOMAIN, f"{serial_number}_meter_{index}")
        for index in range(1, len(solaredge.meters) + 1)
    )

    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if not current.intersection(device.identifiers):
            device_registry.async_remove_device(device.id)


async def async_unload_entry(
    hass: HomeAssistant, entry: SolarEdgeModbusConfigEntry
) -> bool:
    """Unload SolarEdge Modbus config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
