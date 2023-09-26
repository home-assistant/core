"""Tests for Shelly sensor platform."""
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.shelly.const import DOMAIN
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_registry import async_get

from . import (
    init_integration,
    mock_polling_rpc_update,
    mock_rest_update,
    mutate_rpc_device_status,
    register_device,
    register_entity,
)

from tests.common import mock_restore_cache_with_extra_data

RELAY_BLOCK_ID = 0
SENSOR_BLOCK_ID = 3
DEVICE_BLOCK_ID = 4


async def test_block_sensor(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block sensor."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_channel_1_power"
    await init_integration(hass, 1)

    assert hass.states.get(entity_id).state == "53.4"

    monkeypatch.setattr(mock_block_device.blocks[RELAY_BLOCK_ID], "power", 60.1)
    mock_block_device.mock_update()

    assert hass.states.get(entity_id).state == "60.1"


async def test_energy_sensor(hass: HomeAssistant, mock_block_device) -> None:
    """Test energy sensor."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_channel_1_energy"
    await init_integration(hass, 1)

    state = hass.states.get(entity_id)
    # 1234567.89 Wmin / 60 / 1000 = 20.5761315 kWh
    assert state.state == "20.5761315"
    # suggested unit is KWh
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR


async def test_power_factory_unit_migration(
    hass: HomeAssistant, mock_block_device
) -> None:
    """Test migration unit of the power factory sensor."""
    registry = async_get(hass)
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "123456789ABC-emeter_0-powerFactor",
        suggested_object_id="test_name_power_factor",
        unit_of_measurement="%",
    )

    entity_id = f"{SENSOR_DOMAIN}.test_name_power_factor"
    await init_integration(hass, 1)

    state = hass.states.get(entity_id)
    # Value of 0.98 is converted to 98.0%
    assert state.state == "98.0"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE


async def test_power_factory_without_unit_migration(
    hass: HomeAssistant, mock_block_device
) -> None:
    """Test unit and value of the power factory sensor without unit migration."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_power_factor"
    await init_integration(hass, 1)

    state = hass.states.get(entity_id)
    assert state.state == "0.98"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None


async def test_block_rest_sensor(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_block_device, monkeypatch
) -> None:
    """Test block REST sensor."""
    entity_id = register_entity(hass, SENSOR_DOMAIN, "test_name_rssi", "rssi")
    await init_integration(hass, 1)

    assert hass.states.get(entity_id).state == "-64"

    monkeypatch.setitem(mock_block_device.status["wifi_sta"], "rssi", -71)
    await mock_rest_update(hass, freezer)

    assert hass.states.get(entity_id).state == "-71"


async def test_block_sleeping_sensor(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block sleeping sensor."""
    monkeypatch.setattr(
        mock_block_device.blocks[DEVICE_BLOCK_ID], "sensor_ids", {"battery": 98}
    )
    entity_id = f"{SENSOR_DOMAIN}.test_name_temperature"
    await init_integration(hass, 1, sleep_period=1000)

    # Sensor should be created when device is online
    assert hass.states.get(entity_id) is None

    # Make device online
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "22.1"

    monkeypatch.setattr(mock_block_device.blocks[SENSOR_BLOCK_ID], "temp", 23.4)
    mock_block_device.mock_update()

    assert hass.states.get(entity_id).state == "23.4"


async def test_block_restored_sleeping_sensor(
    hass: HomeAssistant, mock_block_device, device_reg, monkeypatch
) -> None:
    """Test block restored sleeping sensor."""
    entry = await init_integration(hass, 1, sleep_period=1000, skip_setup=True)
    register_device(device_reg, entry)
    entity_id = register_entity(
        hass, SENSOR_DOMAIN, "test_name_temperature", "sensor_0-temp", entry
    )
    extra_data = {"native_value": "20.4", "native_unit_of_measurement": "°C"}

    mock_restore_cache_with_extra_data(hass, ((State(entity_id, ""), extra_data),))
    monkeypatch.setattr(mock_block_device, "initialized", False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "20.4"

    # Make device online
    monkeypatch.setattr(mock_block_device, "initialized", True)
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "22.1"


async def test_block_restored_sleeping_sensor_no_last_state(
    hass: HomeAssistant, mock_block_device, device_reg, monkeypatch
) -> None:
    """Test block restored sleeping sensor missing last state."""
    entry = await init_integration(hass, 1, sleep_period=1000, skip_setup=True)
    register_device(device_reg, entry)
    entity_id = register_entity(
        hass, SENSOR_DOMAIN, "test_name_temperature", "sensor_0-temp", entry
    )
    monkeypatch.setattr(mock_block_device, "initialized", False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    # Make device online
    monkeypatch.setattr(mock_block_device, "initialized", True)
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "22.1"


async def test_block_sensor_error(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block sensor unavailable on sensor error."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_battery"
    await init_integration(hass, 1)

    assert hass.states.get(entity_id).state == "98"

    monkeypatch.setattr(mock_block_device.blocks[DEVICE_BLOCK_ID], "battery", -1)
    mock_block_device.mock_update()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_block_sensor_removal(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block sensor is removed due to removal_condition."""
    entity_registry = async_get(hass)
    entity_id = register_entity(
        hass, SENSOR_DOMAIN, "test_name_battery", "device_0-battery"
    )

    assert entity_registry.async_get(entity_id) is not None

    monkeypatch.setitem(mock_block_device.settings, "external_power", 1)
    await init_integration(hass, 1)

    assert entity_registry.async_get(entity_id) is None


async def test_block_not_matched_restored_sleeping_sensor(
    hass: HomeAssistant, mock_block_device, device_reg, monkeypatch
) -> None:
    """Test block not matched to restored sleeping sensor."""
    entry = await init_integration(hass, 1, sleep_period=1000, skip_setup=True)
    register_device(device_reg, entry)
    entity_id = register_entity(
        hass, SENSOR_DOMAIN, "test_name_temperature", "sensor_0-temp", entry
    )
    extra_data = {"native_value": "20.4", "native_unit_of_measurement": "°C"}

    mock_restore_cache_with_extra_data(hass, ((State(entity_id, ""), extra_data),))
    monkeypatch.setattr(mock_block_device, "initialized", False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "20.4"

    # Make device online
    monkeypatch.setattr(mock_block_device.blocks[SENSOR_BLOCK_ID], "type", "other_type")
    monkeypatch.setattr(mock_block_device, "initialized", True)
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "20.4"


async def test_block_sensor_without_value(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block sensor without value is not created."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_battery"
    monkeypatch.setattr(mock_block_device.blocks[DEVICE_BLOCK_ID], "battery", None)
    await init_integration(hass, 1)

    assert hass.states.get(entity_id) is None


async def test_block_sensor_unknown_value(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block sensor unknown value."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_battery"
    await init_integration(hass, 1)

    monkeypatch.setattr(mock_block_device.blocks[DEVICE_BLOCK_ID], "battery", None)
    mock_block_device.mock_update()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN


async def test_rpc_sensor(hass: HomeAssistant, mock_rpc_device, monkeypatch) -> None:
    """Test RPC sensor."""
    entity_id = f"{SENSOR_DOMAIN}.test_cover_0_power"
    await init_integration(hass, 2)

    assert hass.states.get(entity_id).state == "85.3"

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "cover:0", "apower", "88.2")
    mock_rpc_device.mock_update()

    assert hass.states.get(entity_id).state == "88.2"

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "cover:0", "apower", None)
    mock_rpc_device.mock_update()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN


async def test_rpc_illuminance_sensor(
    hass: HomeAssistant, mock_rpc_device, monkeypatch
) -> None:
    """Test RPC illuminacne sensor."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_illuminance"
    await init_integration(hass, 2)

    assert hass.states.get(entity_id).state == "345"


async def test_rpc_sensor_error(
    hass: HomeAssistant, mock_rpc_device, monkeypatch
) -> None:
    """Test RPC sensor unavailable on sensor error."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_voltmeter"
    await init_integration(hass, 2)

    assert hass.states.get(entity_id).state == "4.321"

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "voltmeter", "voltage", None)
    mock_rpc_device.mock_update()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_rpc_polling_sensor(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_rpc_device, monkeypatch
) -> None:
    """Test RPC polling sensor."""
    entity_id = register_entity(hass, SENSOR_DOMAIN, "test_name_rssi", "wifi-rssi")
    await init_integration(hass, 2)

    assert hass.states.get(entity_id).state == "-63"

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "wifi", "rssi", "-70")
    await mock_polling_rpc_update(hass, freezer)

    assert hass.states.get(entity_id).state == "-70"


async def test_rpc_sleeping_sensor(
    hass: HomeAssistant, mock_rpc_device, device_reg, monkeypatch
) -> None:
    """Test RPC online sleeping sensor."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_temperature"
    entry = await init_integration(hass, 2, sleep_period=1000)

    # Sensor should be created when device is online
    assert hass.states.get(entity_id) is None

    register_entity(
        hass,
        SENSOR_DOMAIN,
        "test_name_temperature",
        "temperature:0-temperature_0",
        entry,
    )

    # Make device online
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "22.9"

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "temperature:0", "tC", 23.4)
    mock_rpc_device.mock_update()

    assert hass.states.get(entity_id).state == "23.4"


async def test_rpc_restored_sleeping_sensor(
    hass: HomeAssistant, mock_rpc_device, device_reg, monkeypatch
) -> None:
    """Test RPC restored sensor."""
    entry = await init_integration(hass, 2, sleep_period=1000, skip_setup=True)
    register_device(device_reg, entry)
    entity_id = register_entity(
        hass,
        SENSOR_DOMAIN,
        "test_name_temperature",
        "temperature:0-temperature_0",
        entry,
    )
    extra_data = {"native_value": "21.0", "native_unit_of_measurement": "°C"}

    mock_restore_cache_with_extra_data(hass, ((State(entity_id, ""), extra_data),))
    monkeypatch.setattr(mock_rpc_device, "initialized", False)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "21.0"

    # Make device online
    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "22.9"


async def test_rpc_restored_sleeping_sensor_no_last_state(
    hass: HomeAssistant, mock_rpc_device, device_reg, monkeypatch
) -> None:
    """Test RPC restored sensor missing last state."""
    entry = await init_integration(hass, 2, sleep_period=1000, skip_setup=True)
    register_device(device_reg, entry)
    entity_id = register_entity(
        hass,
        SENSOR_DOMAIN,
        "test_name_temperature",
        "temperature:0-temperature_0",
        entry,
    )

    monkeypatch.setattr(mock_rpc_device, "initialized", False)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    # Make device online
    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "22.9"


async def test_rpc_em1_sensors(
    hass: HomeAssistant, mock_rpc_device, entity_registry_enabled_by_default: None
) -> None:
    """Test RPC sensors for EM1 component."""
    registry = async_get(hass)
    await init_integration(hass, 2)

    state = hass.states.get("sensor.test_name_em0_power")
    assert state
    assert state.state == "85.3"

    entry = registry.async_get("sensor.test_name_em0_power")
    assert entry
    assert entry.unique_id == "123456789ABC-em1:0-power_em1"

    state = hass.states.get("sensor.test_name_em1_power")
    assert state
    assert state.state == "123.3"

    entry = registry.async_get("sensor.test_name_em1_power")
    assert entry
    assert entry.unique_id == "123456789ABC-em1:1-power_em1"

    state = hass.states.get("sensor.test_name_em0_total_active_energy")
    assert state
    assert state.state == "123.4564"

    entry = registry.async_get("sensor.test_name_em0_total_active_energy")
    assert entry
    assert entry.unique_id == "123456789ABC-em1data:0-total_act_energy"

    state = hass.states.get("sensor.test_name_em1_total_active_energy")
    assert state
    assert state.state == "987.6543"

    entry = registry.async_get("sensor.test_name_em1_total_active_energy")
    assert entry
    assert entry.unique_id == "123456789ABC-em1data:1-total_act_energy"
