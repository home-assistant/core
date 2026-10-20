"""Integrate Sofar devices into Home Assistant."""

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from modbus_connection import ModbusTimeoutError
from sofar_modbus.modern.device import BATTERY_STRING_COMPONENTS, SofarInverter

from homeassistant.components.modbus import async_get_unit
from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorExtraStoredData,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_TYPE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    restore_state,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import (
    CONF_UNIT_ID,
    DOMAIN,
    METER_ENERGY,
    SCAN_INTERVAL,
    SETTINGS_SCAN_INTERVAL,
    TYPE_TCP,
)
from .coordinator import SofarConfigEntry, SofarDataUpdateCoordinator, SofarRuntimeData
from .helpers import create_modbus_params
from .sensor import TOTAL_SENSOR_DESCRIPTIONS
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

_REMOVED_SENSOR_KEYS = ("serial_number", "waiting_time")

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@callback
def _async_remove_stale_sensors(hass: HomeAssistant, serial: str) -> None:
    """Drop removed sensors so they don't linger unavailable."""
    registry = er.async_get(hass)
    for key in _REMOVED_SENSOR_KEYS:
        entity_id = registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, f"{serial}_{key}"
        )
        if entity_id is not None:
            registry.async_remove(entity_id)


@callback
def _async_remove_denied_meter_energy(
    hass: HomeAssistant, serial: str, served: frozenset[str]
) -> None:
    """Drop meter sensors a model denies, so they don't linger unavailable."""
    if METER_ENERGY in served:
        return
    registry = er.async_get(hass)
    for description in TOTAL_SENSOR_DESCRIPTIONS:
        if description.component != METER_ENERGY:
            continue
        entity_id = registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, f"{serial}_{description.key}"
        )
        if entity_id is not None:
            registry.async_remove(entity_id)


def _async_seed_high_water_marks(
    hass: HomeAssistant, serial: str, device: SofarInverter
) -> None:
    """Prime high-water marks before the first poll has nothing to compare."""
    registry = er.async_get(hass)
    restore_state_data = restore_state.async_get(hass)
    for description in TOTAL_SENSOR_DESCRIPTIONS:
        entity_id = registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, f"{serial}_{description.key}"
        )
        if (
            entity_id is None
            or (stored := restore_state_data.async_get_stored_state(entity_id)) is None
        ):
            continue
        if stored.extra_data is None:
            continue
        extra = SensorExtraStoredData.from_dict(stored.extra_data.as_dict())
        if extra is None or not isinstance(extra.native_value, (int, float)):
            continue
        description.total_fn(device).seed(float(extra.native_value))


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Sofar integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SofarConfigEntry) -> None:
    """Set up Sofar from a config entry."""
    serial = entry.unique_id
    assert serial is not None
    _async_remove_stale_sensors(hass, serial)

    unit = async_get_unit(
        hass,
        entry,
        create_modbus_params(entry.data),
        entry.data[CONF_UNIT_ID],
    )

    device = SofarInverter(unit, serial_number=serial)
    _async_seed_high_water_marks(hass, serial, device)

    readings = SofarDataUpdateCoordinator(
        hass,
        entry,
        device,
        device.async_update_readings,
        timedelta(seconds=SCAN_INTERVAL),
    )
    settings = SofarDataUpdateCoordinator(
        hass,
        entry,
        device,
        device.async_update_settings,
        timedelta(seconds=SETTINGS_SCAN_INTERVAL),
    )
    try:
        await readings.async_config_entry_first_refresh()
    except ConfigEntryNotReady as err:
        failure = readings.last_exception
        if not (
            device.connected
            and isinstance(failure, UpdateFailed)
            and isinstance(failure.__cause__, ModbusTimeoutError)
        ):
            raise
        _LOGGER.info(
            "%s: inverter is not answering, setting up without it: %s",
            entry.title,
            err,
        )

        @callback
        def _async_reload_once_answered() -> None:
            """Set up again in full once the inverter answers."""
            if readings.last_update_success:
                hass.config_entries.async_schedule_reload(entry.entry_id)

        entry.async_on_unload(readings.async_add_listener(_async_reload_once_answered))
    else:
        await settings.async_refresh()
        # Not tied to a coordinator: identity never changes once read.
        await device.async_read_identity()

    # Up front: a part's device must name an inverter that has an id.
    inverter = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **readings.device_info
    )
    entry.runtime_data = SofarRuntimeData(readings, settings, inverter.id)
    # Until the masks settle the type, nothing is served or denied.
    if device.inverter_type:
        _async_remove_denied_meter_energy(
            hass, serial, entry.runtime_data.served_components
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


def _battery_pack_number(serial: str, identifier: str) -> int | None:
    """The battery pack a device identifier names, if it names one."""
    prefix = f"{serial}_battery_"
    if not identifier.startswith(prefix):
        return None
    suffix = identifier.removeprefix(prefix)
    number = int(suffix) if suffix.isdecimal() else None
    return number if number in BATTERY_STRING_COMPONENTS else None


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: SofarConfigEntry,
    device_entry: dr.AnyDeviceEntry,
) -> bool:
    """Allow removing a battery pack the inverter no longer reports."""
    serial = config_entry.unique_id
    if TYPE_CHECKING:
        assert serial is not None
    runtime_data = (
        config_entry.runtime_data
        if config_entry.state is ConfigEntryState.LOADED
        else None
    )
    packs: set[int] = set()
    for domain, identifier in device_entry.identifiers:
        if domain != DOMAIN:
            continue
        if identifier == serial or identifier.startswith(f"{serial}_pv_string_"):
            return False
        if (number := _battery_pack_number(serial, identifier)) is None:
            continue
        if (
            runtime_data is not None
            and number in runtime_data.readings.device.wired_battery_strings
        ):
            return False
        packs.add(number)

    if runtime_data is not None:
        runtime_data.wired_packs -= packs
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: SofarConfigEntry) -> None:
    """Migrate an old config entry."""
    if entry.version == 1 and entry.minor_version == 1:
        hass.config_entries.async_update_entry(
            entry, data={CONF_TYPE: TYPE_TCP, **entry.data}, minor_version=2
        )


async def async_unload_entry(hass: HomeAssistant, entry: SofarConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
