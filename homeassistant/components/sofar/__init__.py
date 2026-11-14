"""Integrate Sofar devices into Home Assistant."""

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from sofar_modbus import (
    BATTERY_PACKS,
    BATTERY_STRING_COMPONENTS,
    PV_STRING_COMPONENTS,
    InverterSilentError,
    SofarInverter,
)

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
    FAULT_LOG,
    PACKS_SCAN_INTERVAL,
    SCAN_INTERVAL,
    SERVED_COMPONENTS,
    SETTINGS_SCAN_INTERVAL,
    TYPE_TCP,
)
from .coordinator import SofarConfigEntry, SofarDataUpdateCoordinator, SofarRuntimeData
from .entity import (
    SofarPart,
    battery_pack_identifier,
    entity_unique_id,
    part_identifier,
)
from .helpers import create_modbus_params
from .sensor import TOTAL_SENSOR_DESCRIPTIONS, restored_total
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
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
            SENSOR_DOMAIN, DOMAIN, entity_unique_id(serial, key)
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
            SENSOR_DOMAIN, DOMAIN, entity_unique_id(serial, description.key)
        )
        if (
            entity_id is None
            or (stored := restore_state_data.async_get_stored_state(entity_id)) is None
            or stored.extra_data is None
            or (
                total := restored_total(
                    SensorExtraStoredData.from_dict(stored.extra_data.as_dict())
                )
            )
            is None
        ):
            continue
        description.total_fn(device).seed(total)


@callback
def _async_store_served(
    hass: HomeAssistant, entry: SofarConfigEntry, served: frozenset[str]
) -> None:
    """Remember what the inverter serves for a setup it sleeps through."""
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, SERVED_COMPONENTS: sorted(served)}
    )


async def _async_refresh_versions(hass: HomeAssistant, entry: SofarConfigEntry) -> None:
    """Read the firmware versions a setup without the inverter missed."""
    await entry.runtime_data.readings.device.async_read_identity()
    dr.async_get(hass).async_get_or_create_from_info(
        config_entry_id=entry.entry_id,
        device_info=entry.runtime_data.readings.device_info,
    )


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

    stored = entry.data.get(SERVED_COMPONENTS, ())
    device = SofarInverter(
        unit,
        serial_number=serial,
        has_fault_log=FAULT_LOG in stored,
        has_battery_tower=BATTERY_PACKS in stored,
    )
    _async_seed_high_water_marks(hass, serial, device)

    readings = SofarDataUpdateCoordinator(
        hass,
        entry,
        entry.title,
        device,
        device.async_update_readings,
        timedelta(seconds=SCAN_INTERVAL),
    )
    settings = SofarDataUpdateCoordinator(
        hass,
        entry,
        entry.title,
        device,
        device.async_update_settings,
        timedelta(seconds=SETTINGS_SCAN_INTERVAL),
    )
    packs = SofarDataUpdateCoordinator(
        hass,
        entry,
        f"{entry.title} battery packs",
        device,
        device.async_update_packs,
        timedelta(seconds=PACKS_SCAN_INTERVAL),
    )
    try:
        await readings.async_config_entry_first_refresh()
    except ConfigEntryNotReady as err:
        if not (
            isinstance(readings.last_exception, UpdateFailed)
            and isinstance(readings.last_exception.__cause__, InverterSilentError)
        ):
            raise
        _LOGGER.info(
            "%s: inverter is not answering, setting up without it: %s",
            entry.title,
            err,
        )

        served = frozenset(
            entry.data.get(SERVED_COMPONENTS, device.expected_components)
        )

        @callback
        def _async_settle_on_first_answer() -> None:
            """Take in what the inverter serves once it answers."""
            remove_listener()
            _async_store_served(hass, entry, device.expected_components)
            if device.expected_components != served:
                hass.config_entries.async_schedule_reload(entry.entry_id)
                return
            entry.async_create_background_task(
                hass, _async_refresh_versions(hass, entry), "sofar_refresh_versions"
            )

        remove_listener = readings.async_add_listener(_async_settle_on_first_answer)
    else:
        await settings.async_refresh()
        if BATTERY_PACKS in device.expected_components:
            await packs.async_refresh()
        # Not tied to a coordinator: identity never changes once read.
        await device.async_read_identity()
        served = device.expected_components
        _async_store_served(hass, entry, served)

    # Up front: a part's device must name an inverter that has an id.
    inverter = dr.async_get(hass).async_get_or_create_from_info(
        config_entry_id=entry.entry_id, device_info=readings.device_info
    )
    entry.runtime_data = SofarRuntimeData(
        readings, settings, packs, inverter.id, served
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: SofarConfigEntry,
    device_entry: dr.AnyDeviceEntry,
) -> bool:
    """Allow removing a battery string or pack the inverter no longer reports."""
    serial = config_entry.unique_id
    if TYPE_CHECKING:
        assert serial is not None
    if (DOMAIN, serial) in device_entry.identifiers or any(
        (DOMAIN, part_identifier(serial, SofarPart("pv_string", number)))
        in device_entry.identifiers
        for number in PV_STRING_COMPONENTS
    ):
        return False
    strings = {
        number
        for number in BATTERY_STRING_COMPONENTS
        if (DOMAIN, part_identifier(serial, SofarPart("battery", number)))
        in device_entry.identifiers
    }
    if config_entry.state is not ConfigEntryState.LOADED:
        return True
    packs = {
        place: pack
        for place, pack in config_entry.runtime_data.readings.device.battery_packs.items()
        if (DOMAIN, battery_pack_identifier(serial, pack)) in device_entry.identifiers
    }
    if strings & config_entry.runtime_data.readings.device.wired_battery_strings or any(
        pack.answered for pack in packs.values()
    ):
        return False
    config_entry.runtime_data.added_battery_strings -= strings
    config_entry.runtime_data.added_battery_packs -= packs.keys()
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
