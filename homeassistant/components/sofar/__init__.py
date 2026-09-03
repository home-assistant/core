"""Integrate Sofar devices into Home Assistant."""

from datetime import timedelta
import logging

from modbus_connection import ModbusError, ModbusTcpParams
from sofar_modbus.modern.device import SofarInverter, identify

from homeassistant.components.modbus import async_get_unit
from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorExtraStoredData,
    SensorStateClass,
)
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    restore_state,
)

from .const import CONF_UNIT_ID, DOMAIN, SCAN_INTERVAL, SETTINGS_SCAN_INTERVAL
from .coordinator import SofarConfigEntry, SofarDataUpdateCoordinator, SofarRuntimeData
from .sensor import SENSOR_DESCRIPTIONS

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

_IDENTITY_ATTEMPTS = 3


def _async_remove_stale_waiting_time(hass: HomeAssistant, serial: str) -> None:
    """Drop the removed waiting-time entity so it doesn't linger unavailable."""
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{serial}_waiting_time"
    )
    if entity_id is not None:
        registry.async_remove(entity_id)


async def _async_read_identity(entry: SofarConfigEntry, device: SofarInverter) -> None:
    """Read identity once, retrying a few times against a transient blip."""
    for attempt in range(_IDENTITY_ATTEMPTS):
        try:
            await device.identity.async_update()
        except ModbusError as err:
            if attempt == _IDENTITY_ATTEMPTS - 1:
                _LOGGER.warning("%s: could not read identity: %s", entry.title, err)
        else:
            return


def _async_seed_high_water_marks(
    hass: HomeAssistant, serial: str, device: SofarInverter
) -> None:
    """Prime high-water marks before the first poll has nothing to compare."""
    registry = er.async_get(hass)
    last_states = restore_state.async_get(hass).last_states
    for description in SENSOR_DESCRIPTIONS:
        if description.state_class is not SensorStateClass.TOTAL_INCREASING:
            continue
        entity_id = registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, f"{serial}_{description.key}"
        )
        if entity_id is None or (stored := last_states.get(entity_id)) is None:
            continue
        if stored.extra_data is None:
            continue
        extra = SensorExtraStoredData.from_dict(stored.extra_data.as_dict())
        if extra is None or not isinstance(extra.native_value, (int, float)):
            continue
        getattr(device, description.component).seed_high_water(
            description.key, float(extra.native_value)
        )


async def async_setup_entry(hass: HomeAssistant, entry: SofarConfigEntry) -> bool:
    """Set up Sofar Inverter Modbus from a config entry."""
    serial = entry.unique_id
    assert serial is not None
    _async_remove_stale_waiting_time(hass, serial)
    inverter_type, model = identify(serial)
    if not inverter_type:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="unrecognized_inverter_model",
            translation_placeholders={"title": entry.title},
        )

    unit = async_get_unit(
        hass,
        entry,
        ModbusTcpParams(host=entry.data[CONF_HOST], port=entry.data[CONF_PORT]),
        entry.data[CONF_UNIT_ID],
    )

    device = SofarInverter(
        unit,
        serial_number=serial,
        model=model,
        inverter_type=inverter_type,
    )
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
    await readings.async_config_entry_first_refresh()
    await settings.async_refresh()

    # Not tied to a coordinator: identity never changes once read.
    await _async_read_identity(entry, device)

    # Up front: a part's device must name an inverter that has an id.
    inverter = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **readings.device_info
    )
    entry.runtime_data = SofarRuntimeData(readings, settings, inverter.id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SofarConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
