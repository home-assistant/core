"""Tests for the SMA Modbus sensor entities."""

from unittest.mock import AsyncMock, patch

from modbus_connection.mock import MockModbusConnection
from sma_modbus import DeviceType, Vendor
from sma_modbus.home_manager import SystemStatus
from sma_modbus.testing import set_input_registers

from homeassistant.components.sma_modbus.const import DOMAIN
from homeassistant.components.sma_modbus.coordinator import SmaCoordinator
from homeassistant.components.sma_modbus.sensor import SENSOR_DESCRIPTIONS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    HOST,
    SERIAL,
    make_config_entry,
    make_seeded_connection,
    mock_discovery_info,
)

from tests.common import MockConfigEntry

DEVICE_TYPE = DeviceType.SUNNY_BOY_SMART_ENERGY


async def _setup_entry(
    hass: HomeAssistant,
    device_type: DeviceType = DEVICE_TYPE,
) -> tuple[MockConfigEntry, MockModbusConnection]:
    """Set up the integration and return the entry and connection."""
    connection = make_seeded_connection(device_type)
    entry = make_config_entry(device_type)
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.sma_modbus.ModbusUnitConnection",
            return_value=connection,
        ),
        patch(
            "homeassistant.components.sma_modbus.discover",
            AsyncMock(return_value=mock_discovery_info(device_type)),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    return entry, connection


async def test_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the device registry entry is created with the right info."""
    entry, _ = await _setup_entry(hass)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry.unique_id), entry.entry_id
    )
    assert device is not None
    assert device.manufacturer == Vendor.SMA.name
    assert device.name == f"SMA{SERIAL}"
    # Sunny Boy Smart Energy model 19085 -> SBSE_6_0
    assert device.model == "Sunny Boy Smart Energy 6.0"
    assert device.serial_number == str(SERIAL)
    assert device.configuration_url == f"http://{HOST}:80"


async def test_device_info_web_port_https(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the configuration_url uses https when web port is 443."""
    connection = make_seeded_connection(DEVICE_TYPE)
    entry = make_config_entry(DEVICE_TYPE, extra_data={"web_port": 443})
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.sma_modbus.ModbusUnitConnection",
            return_value=connection,
        ),
        patch(
            "homeassistant.components.sma_modbus.discover",
            AsyncMock(return_value=mock_discovery_info(DEVICE_TYPE)),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry.unique_id), entry.entry_id
    )
    assert device is not None
    assert device.configuration_url == f"https://{HOST}:443"


async def test_sensor_entity_count(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the correct number of sensor entities are created."""
    entry, _ = await _setup_entry(hass)

    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entities) == len(SENSOR_DESCRIPTIONS[DEVICE_TYPE])


async def test_sensor_enum_value(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an enum sensor returns the lowercase member name."""
    entry, connection = await _setup_entry(hass)

    # Seed system_status with SystemStatus.OK (307) and refresh
    device = entry.runtime_data.device
    set_input_registers(connection, device, {"system_status": SystemStatus.OK.value})
    await device.async_update()

    coordinator: SmaCoordinator = entry.runtime_data
    coordinator.async_set_updated_data(device)

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.unique_id}-system_status"
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "ok"


async def test_sensor_numeric_value(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a numeric sensor returns the rounded value."""
    entry, connection = await _setup_entry(hass)

    device = entry.runtime_data.device
    set_input_registers(connection, device, {"ac_power": 5000})
    await device.async_update()

    coordinator: SmaCoordinator = entry.runtime_data
    coordinator.async_set_updated_data(device)

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.unique_id}-ac_power"
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "5000"


async def test_sensor_nan_value_is_none(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a sensor with a NaN sentinel returns unknown."""
    entry, connection = await _setup_entry(hass)

    device = entry.runtime_data.device
    set_input_registers(connection, device, {"ac_power": None})
    await device.async_update()

    coordinator: SmaCoordinator = entry.runtime_data
    coordinator.async_set_updated_data(device)

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.unique_id}-ac_power"
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state is None or state.state == "unknown"


async def test_sensor_unique_ids(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor unique IDs are based on the config entry unique id."""
    entry, _ = await _setup_entry(hass)

    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entities) > 0
    for entity in entities:
        assert entity.unique_id.startswith(f"{entry.unique_id}-")


async def test_sensor_device_class(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test power sensor has the power device class."""
    entry, _ = await _setup_entry(hass)

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.unique_id}-ac_power"
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes.get("device_class") == "power"
