"""Tests for Shelly sensor platform."""

from copy import deepcopy
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.sensor import (
    ATTR_OPTIONS,
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.shelly.const import DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.setup import async_setup_component

from . import (
    get_entity_state,
    init_integration,
    mock_polling_rpc_update,
    mock_rest_update,
    mutate_rpc_device_status,
    register_device,
    register_entity,
)

from tests.common import async_fire_time_changed, mock_restore_cache_with_extra_data

RELAY_BLOCK_ID = 0
SENSOR_BLOCK_ID = 3
DEVICE_BLOCK_ID = 4


async def test_block_sensor(
    hass: HomeAssistant,
    mock_block_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block sensor."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_channel_1_power"
    await init_integration(hass, 1)

    assert hass.states.get(entity_id).state == "53.4"

    monkeypatch.setattr(mock_block_device.blocks[RELAY_BLOCK_ID], "power", 60.1)
    mock_block_device.mock_update()

    assert hass.states.get(entity_id).state == "60.1"

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-relay_0-power"


async def test_energy_sensor(
    hass: HomeAssistant, mock_block_device: Mock, entity_registry: EntityRegistry
) -> None:
    """Test energy sensor."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_channel_1_energy"
    await init_integration(hass, 1)

    state = hass.states.get(entity_id)
    # 1234567.89 Wmin / 60 / 1000 = 20.5761315 kWh
    assert state.state == "20.5761315"
    # suggested unit is KWh
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-relay_0-energy"


async def test_power_factory_unit_migration(
    hass: HomeAssistant, mock_block_device: Mock, entity_registry: EntityRegistry
) -> None:
    """Test migration unit of the power factory sensor."""
    entity_registry.async_get_or_create(
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

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-emeter_0-powerFactor"


async def test_power_factory_without_unit_migration(
    hass: HomeAssistant, mock_block_device: Mock, entity_registry: EntityRegistry
) -> None:
    """Test unit and value of the power factory sensor without unit migration."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_power_factor"
    await init_integration(hass, 1)

    state = hass.states.get(entity_id)
    assert state.state == "0.98"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-emeter_0-powerFactor"


async def test_block_rest_sensor(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block REST sensor."""
    entity_id = register_entity(hass, SENSOR_DOMAIN, "test_name_rssi", "rssi")
    await init_integration(hass, 1)

    assert hass.states.get(entity_id).state == "-64"

    monkeypatch.setitem(mock_block_device.status["wifi_sta"], "rssi", -71)
    await mock_rest_update(hass, freezer)

    assert hass.states.get(entity_id).state == "-71"


async def test_block_sleeping_sensor(
    hass: HomeAssistant,
    mock_block_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
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
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == "22.1"

    monkeypatch.setattr(mock_block_device.blocks[SENSOR_BLOCK_ID], "temp", 23.4)
    mock_block_device.mock_update()

    assert hass.states.get(entity_id).state == "23.4"

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-sensor_0-temp"


async def test_block_restored_sleeping_sensor(
    hass: HomeAssistant,
    mock_block_device: Mock,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block restored sleeping sensor."""
    entry = await init_integration(hass, 1, sleep_period=1000, skip_setup=True)
    device = register_device(device_registry, entry)
    entity_id = register_entity(
        hass,
        SENSOR_DOMAIN,
        "test_name_temperature",
        "sensor_0-temp",
        entry,
        device_id=device.id,
    )
    extra_data = {"native_value": "20.4", "native_unit_of_measurement": "°C"}

    mock_restore_cache_with_extra_data(hass, ((State(entity_id, ""), extra_data),))
    monkeypatch.setattr(mock_block_device, "initialized", False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "20.4"
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE

    # Make device online
    monkeypatch.setattr(mock_block_device, "initialized", True)
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == "22.1"


async def test_block_restored_sleeping_sensor_no_last_state(
    hass: HomeAssistant,
    mock_block_device: Mock,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block restored sleeping sensor missing last state."""
    entry = await init_integration(hass, 1, sleep_period=1000, skip_setup=True)
    device = register_device(device_registry, entry)
    entity_id = register_entity(
        hass,
        SENSOR_DOMAIN,
        "test_name_temperature",
        "sensor_0-temp",
        entry,
        device_id=device.id,
    )
    monkeypatch.setattr(mock_block_device, "initialized", False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    # Make device online
    monkeypatch.setattr(mock_block_device, "initialized", True)
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == "22.1"


async def test_block_sensor_error(
    hass: HomeAssistant,
    mock_block_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block sensor unavailable on sensor error."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_battery"
    await init_integration(hass, 1)

    assert hass.states.get(entity_id).state == "98"

    monkeypatch.setattr(mock_block_device.blocks[DEVICE_BLOCK_ID], "battery", -1)
    mock_block_device.mock_update()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-device_0-battery"


async def test_block_sensor_removal(
    hass: HomeAssistant,
    mock_block_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block sensor is removed due to removal_condition."""
    entity_id = register_entity(
        hass, SENSOR_DOMAIN, "test_name_battery", "device_0-battery"
    )

    assert entity_registry.async_get(entity_id) is not None

    monkeypatch.setitem(mock_block_device.settings, "external_power", 1)
    await init_integration(hass, 1)

    assert entity_registry.async_get(entity_id) is None


async def test_block_not_matched_restored_sleeping_sensor(
    hass: HomeAssistant,
    mock_block_device: Mock,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block not matched to restored sleeping sensor."""
    entry = await init_integration(hass, 1, sleep_period=1000, skip_setup=True)
    device = register_device(device_registry, entry)
    entity_id = register_entity(
        hass,
        SENSOR_DOMAIN,
        "test_name_temperature",
        "sensor_0-temp",
        entry,
        device_id=device.id,
    )
    extra_data = {"native_value": "20.4", "native_unit_of_measurement": "°C"}

    mock_restore_cache_with_extra_data(hass, ((State(entity_id, ""), extra_data),))
    monkeypatch.setattr(mock_block_device, "initialized", False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "20.4"

    # Make device online
    monkeypatch.setattr(
        mock_block_device.blocks[SENSOR_BLOCK_ID], "description", "other_desc"
    )
    monkeypatch.setattr(mock_block_device, "initialized", True)
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == "20.4"


async def test_block_sensor_without_value(
    hass: HomeAssistant, mock_block_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test block sensor without value is not created."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_battery"
    monkeypatch.setattr(mock_block_device.blocks[DEVICE_BLOCK_ID], "battery", None)
    await init_integration(hass, 1)

    assert hass.states.get(entity_id) is None


async def test_block_sensor_unknown_value(
    hass: HomeAssistant, mock_block_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test block sensor unknown value."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_battery"
    await init_integration(hass, 1)

    monkeypatch.setattr(mock_block_device.blocks[DEVICE_BLOCK_ID], "battery", None)
    mock_block_device.mock_update()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN


async def test_rpc_sensor(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_rpc_rssi_sensor_removal(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC RSSI sensor removal if no WiFi stations enabled."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_rssi"
    entry = await init_integration(hass, 2)

    # WiFi1 enabled, do not remove sensor
    assert get_entity_state(hass, entity_id) == "-63"

    # WiFi1 & WiFi2 disabled - remove sensor
    monkeypatch.setitem(mock_rpc_device.config["wifi"]["sta"], "enable", False)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id) is None

    # WiFi2 enabled, do not remove sensor
    monkeypatch.setitem(mock_rpc_device.config["wifi"]["sta1"], "enable", True)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert get_entity_state(hass, entity_id) == "-63"


async def test_rpc_illuminance_sensor(
    hass: HomeAssistant, mock_rpc_device: Mock, entity_registry: EntityRegistry
) -> None:
    """Test RPC illuminacne sensor."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_illuminance"
    await init_integration(hass, 2)

    assert hass.states.get(entity_id).state == "345"

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-illuminance:0-illuminance"


async def test_rpc_sensor_error(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC sensor unavailable on sensor error."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_voltmeter"
    await init_integration(hass, 2)

    assert hass.states.get(entity_id).state == "4.321"

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "voltmeter", "voltage", None)
    mock_rpc_device.mock_update()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-voltmeter-voltmeter"


async def test_rpc_polling_sensor(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC polling sensor."""
    entity_id = register_entity(hass, SENSOR_DOMAIN, "test_name_rssi", "wifi-rssi")
    await init_integration(hass, 2)

    assert hass.states.get(entity_id).state == "-63"

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "wifi", "rssi", "-70")
    await mock_polling_rpc_update(hass, freezer)

    assert hass.states.get(entity_id).state == "-70"

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-wifi-rssi"


async def test_rpc_sleeping_sensor(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC online sleeping sensor."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_temperature"
    monkeypatch.setattr(mock_rpc_device, "connected", False)
    monkeypatch.setitem(mock_rpc_device.status["sys"], "wakeup_period", 1000)
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
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == "22.9"

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "temperature:0", "tC", 23.4)
    mock_rpc_device.mock_update()

    assert hass.states.get(entity_id).state == "23.4"


async def test_rpc_restored_sleeping_sensor(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC restored sensor."""
    entry = await init_integration(hass, 2, sleep_period=1000, skip_setup=True)
    device = register_device(device_registry, entry)
    entity_id = register_entity(
        hass,
        SENSOR_DOMAIN,
        "test_name_temperature",
        "temperature:0-temperature_0",
        entry,
        device_id=device.id,
    )
    extra_data = {"native_value": "21.0", "native_unit_of_measurement": "°C"}

    mock_restore_cache_with_extra_data(hass, ((State(entity_id, ""), extra_data),))
    monkeypatch.setattr(mock_rpc_device, "initialized", False)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "21.0"

    # Make device online
    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    # Mock update
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "22.9"


async def test_rpc_restored_sleeping_sensor_no_last_state(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC restored sensor missing last state."""
    entry = await init_integration(hass, 2, sleep_period=1000, skip_setup=True)
    device = register_device(device_registry, entry)
    entity_id = register_entity(
        hass,
        SENSOR_DOMAIN,
        "test_name_temperature",
        "temperature:0-temperature_0",
        entry,
        device_id=device.id,
    )

    monkeypatch.setattr(mock_rpc_device, "initialized", False)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    # Make device online
    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    # Mock update
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "22.9"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_rpc_em1_sensors(
    hass: HomeAssistant, entity_registry: EntityRegistry, mock_rpc_device: Mock
) -> None:
    """Test RPC sensors for EM1 component."""
    await init_integration(hass, 2)

    state = hass.states.get("sensor.test_name_em0_power")
    assert state
    assert state.state == "85.3"

    entry = entity_registry.async_get("sensor.test_name_em0_power")
    assert entry
    assert entry.unique_id == "123456789ABC-em1:0-power_em1"

    state = hass.states.get("sensor.test_name_em1_power")
    assert state
    assert state.state == "123.3"

    entry = entity_registry.async_get("sensor.test_name_em1_power")
    assert entry
    assert entry.unique_id == "123456789ABC-em1:1-power_em1"

    state = hass.states.get("sensor.test_name_em0_total_active_energy")
    assert state
    assert state.state == "123.4564"

    entry = entity_registry.async_get("sensor.test_name_em0_total_active_energy")
    assert entry
    assert entry.unique_id == "123456789ABC-em1data:0-total_act_energy"

    state = hass.states.get("sensor.test_name_em1_total_active_energy")
    assert state
    assert state.state == "987.6543"

    entry = entity_registry.async_get("sensor.test_name_em1_total_active_energy")
    assert entry
    assert entry.unique_id == "123456789ABC-em1data:1-total_act_energy"


async def test_rpc_sleeping_update_entity_service(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test RPC sleeping device when the update_entity service is used."""
    await async_setup_component(hass, "homeassistant", {})

    entity_id = f"{SENSOR_DOMAIN}.test_name_temperature"
    monkeypatch.setattr(mock_rpc_device, "connected", False)
    monkeypatch.setitem(mock_rpc_device.status["sys"], "wakeup_period", 1000)
    await init_integration(hass, 2, sleep_period=1000)

    # Entity should be created when device is online
    assert hass.states.get(entity_id) is None

    # Make device online
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state.state == "22.9"

    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        service_data={ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    # Entity should be available after update_entity service call
    state = hass.states.get(entity_id)
    assert state.state == "22.9"

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-temperature:0-temperature_0"

    assert (
        "Entity sensor.test_name_temperature comes from a sleeping device"
        in caplog.text
    )


async def test_block_sleeping_update_entity_service(
    hass: HomeAssistant,
    mock_block_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test block sleeping device when the update_entity service is used."""
    await async_setup_component(hass, "homeassistant", {})

    entity_id = f"{SENSOR_DOMAIN}.test_name_temperature"
    monkeypatch.setitem(
        mock_block_device.settings,
        "sleep_mode",
        {"period": 60, "unit": "m"},
    )
    await init_integration(hass, 1, sleep_period=3600)

    # Sensor should be created when device is online
    assert hass.states.get(entity_id) is None

    # Make device online
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == "22.1"

    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        service_data={ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    # Entity should be available after update_entity service call
    state = hass.states.get(entity_id)
    assert state.state == "22.1"

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-sensor_0-temp"

    assert (
        "Entity sensor.test_name_temperature comes from a sleeping device"
        in caplog.text
    )


@pytest.mark.parametrize(
    ("original_unit", "expected_unit"),
    [
        ("m/s", "m/s"),
        (None, None),
        ("", None),
    ],
)
async def test_rpc_analog_input_sensors(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
    original_unit: str | None,
    expected_unit: str | None,
) -> None:
    """Test RPC analog input xpercent sensor."""
    config = deepcopy(mock_rpc_device.config)
    config["input:1"]["xpercent"] = {"expr": "x*0.2995", "unit": original_unit}
    monkeypatch.setattr(mock_rpc_device, "config", config)

    await init_integration(hass, 2)

    entity_id = f"{SENSOR_DOMAIN}.test_name_input_1_analog"
    assert hass.states.get(entity_id).state == "89"

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-input:1-analoginput"

    entity_id = f"{SENSOR_DOMAIN}.test_name_input_1_analog_value"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "8.9"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == expected_unit

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-input:1-analoginput_xpercent"


async def test_rpc_disabled_analog_input_sensors(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test RPC disabled counter sensor."""
    new_config = deepcopy(mock_rpc_device.config)
    new_config["input:1"]["enable"] = False
    monkeypatch.setattr(mock_rpc_device, "config", new_config)

    await init_integration(hass, 2)

    entity_id = f"{SENSOR_DOMAIN}.test_name_input_1_analog"
    assert hass.states.get(entity_id) is None

    entity_id = f"{SENSOR_DOMAIN}.test_name_input_1_analog_value"
    assert hass.states.get(entity_id) is None


async def test_rpc_disabled_xpercent(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test RPC empty xpercent value."""
    mutate_rpc_device_status(
        monkeypatch,
        mock_rpc_device,
        "input:1",
        "xpercent",
        None,
    )
    await init_integration(hass, 2)

    entity_id = f"{SENSOR_DOMAIN}.test_name_input_1_analog"
    assert hass.states.get(entity_id).state == "89"

    entity_id = f"{SENSOR_DOMAIN}.test_name_input_1_analog_value"
    assert hass.states.get(entity_id) is None


@pytest.mark.parametrize(
    ("original_unit", "expected_unit"),
    [
        ("l/h", "l/h"),
        (None, None),
        ("", None),
    ],
)
async def test_rpc_pulse_counter_sensors(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
    original_unit: str | None,
    expected_unit: str | None,
) -> None:
    """Test RPC counter sensor."""
    config = deepcopy(mock_rpc_device.config)
    config["input:2"]["xcounts"] = {"expr": "x/10", "unit": original_unit}
    monkeypatch.setattr(mock_rpc_device, "config", config)

    await init_integration(hass, 2)

    entity_id = f"{SENSOR_DOMAIN}.gas_pulse_counter"
    state = hass.states.get(entity_id)
    assert state.state == "56174"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "pulse"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-input:2-pulse_counter"

    entity_id = f"{SENSOR_DOMAIN}.gas_counter_value"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "561.74"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == expected_unit

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-input:2-counter_value"


async def test_rpc_disabled_pulse_counter_sensors(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test RPC disabled counter sensor."""
    new_config = deepcopy(mock_rpc_device.config)
    new_config["input:2"]["enable"] = False
    monkeypatch.setattr(mock_rpc_device, "config", new_config)

    await init_integration(hass, 2)

    entity_id = f"{SENSOR_DOMAIN}.gas_pulse_counter"
    assert hass.states.get(entity_id) is None

    entity_id = f"{SENSOR_DOMAIN}.gas_counter_value"
    assert hass.states.get(entity_id) is None


async def test_rpc_disabled_xtotal_counter(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test RPC disabled xtotal counter."""
    mutate_rpc_device_status(
        monkeypatch,
        mock_rpc_device,
        "input:2",
        "counts",
        {"total": 20635},
    )
    await init_integration(hass, 2)

    entity_id = f"{SENSOR_DOMAIN}.gas_pulse_counter"
    assert hass.states.get(entity_id).state == "20635"

    entity_id = f"{SENSOR_DOMAIN}.gas_counter_value"
    assert hass.states.get(entity_id) is None


@pytest.mark.parametrize(
    ("original_unit", "expected_unit"),
    [
        ("W", "W"),
        (None, None),
        ("", None),
    ],
)
async def test_rpc_pulse_counter_frequency_sensors(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
    original_unit: str | None,
    expected_unit: str | None,
) -> None:
    """Test RPC counter sensor."""
    config = deepcopy(mock_rpc_device.config)
    config["input:2"]["xfreq"] = {"expr": "x**2", "unit": original_unit}
    monkeypatch.setattr(mock_rpc_device, "config", config)

    await init_integration(hass, 2)

    entity_id = f"{SENSOR_DOMAIN}.gas_pulse_counter_frequency"
    state = hass.states.get(entity_id)
    assert state.state == "208.0"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfFrequency.HERTZ
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-input:2-counter_frequency"

    entity_id = f"{SENSOR_DOMAIN}.gas_pulse_counter_frequency_value"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "6.11"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == expected_unit

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-input:2-counter_frequency_value"


async def test_rpc_disabled_xfreq(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC input with the xfreq sensor disabled."""
    status = deepcopy(mock_rpc_device.status)
    status["input:2"] = {
        "id": 2,
        "counts": {"total": 56174, "xtotal": 561.74},
        "freq": 208.00,
    }
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 2)

    entity_id = f"{SENSOR_DOMAIN}.gas_pulse_counter_frequency_value"

    state = hass.states.get(entity_id)
    assert not state

    entry = entity_registry.async_get(entity_id)
    assert not entry


@pytest.mark.parametrize(
    ("name", "entity_id"),
    [
        ("Virtual sensor", "sensor.test_name_virtual_sensor"),
        (None, "sensor.test_name_text_203"),
    ],
)
async def test_rpc_device_virtual_text_sensor(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    name: str | None,
    entity_id: str,
) -> None:
    """Test a virtual text sensor for RPC device."""
    config = deepcopy(mock_rpc_device.config)
    config["text:203"] = {
        "name": name,
        "meta": {"ui": {"view": "label"}},
    }
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["text:203"] = {"value": "lorem ipsum"}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 3)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "lorem ipsum"

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-text:203-text"

    monkeypatch.setitem(mock_rpc_device.status["text:203"], "value", "dolor sit amet")
    mock_rpc_device.mock_update()
    assert hass.states.get(entity_id).state == "dolor sit amet"


async def test_rpc_remove_text_virtual_sensor_when_mode_field(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test if the virtual text sensor will be removed if the mode has been changed to a field."""
    config = deepcopy(mock_rpc_device.config)
    config["text:200"] = {"name": None, "meta": {"ui": {"view": "field"}}}
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["text:200"] = {"value": "lorem ipsum"}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    config_entry = await init_integration(hass, 3, skip_setup=True)
    device_entry = register_device(device_registry, config_entry)
    entity_id = register_entity(
        hass,
        SENSOR_DOMAIN,
        "test_name_text_200",
        "text:200-text",
        config_entry,
        device_id=device_entry.id,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entry = entity_registry.async_get(entity_id)
    assert not entry


async def test_rpc_remove_text_virtual_sensor_when_orphaned(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    mock_rpc_device: Mock,
) -> None:
    """Check whether the virtual text sensor will be removed if it has been removed from the device configuration."""
    config_entry = await init_integration(hass, 3, skip_setup=True)
    device_entry = register_device(device_registry, config_entry)
    entity_id = register_entity(
        hass,
        SENSOR_DOMAIN,
        "test_name_text_200",
        "text:200-text",
        config_entry,
        device_id=device_entry.id,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entry = entity_registry.async_get(entity_id)
    assert not entry


@pytest.mark.parametrize(
    ("name", "entity_id", "original_unit", "expected_unit"),
    [
        ("Virtual number sensor", "sensor.test_name_virtual_number_sensor", "W", "W"),
        (None, "sensor.test_name_number_203", "", None),
    ],
)
async def test_rpc_device_virtual_number_sensor(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    name: str | None,
    entity_id: str,
    original_unit: str,
    expected_unit: str | None,
) -> None:
    """Test a virtual number sensor for RPC device."""
    config = deepcopy(mock_rpc_device.config)
    config["number:203"] = {
        "name": name,
        "min": 0,
        "max": 100,
        "meta": {"ui": {"step": 0.1, "unit": original_unit, "view": "label"}},
    }
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["number:203"] = {"value": 34.5}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 3)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "34.5"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == expected_unit

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-number:203-number"

    monkeypatch.setitem(mock_rpc_device.status["number:203"], "value", 56.7)
    mock_rpc_device.mock_update()
    assert hass.states.get(entity_id).state == "56.7"


async def test_rpc_remove_number_virtual_sensor_when_mode_field(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test if the virtual number sensor will be removed if the mode has been changed to a field."""
    config = deepcopy(mock_rpc_device.config)
    config["number:200"] = {
        "name": None,
        "min": 0,
        "max": 100,
        "meta": {"ui": {"step": 1, "unit": "", "view": "field"}},
    }
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["number:200"] = {"value": 67.8}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    config_entry = await init_integration(hass, 3, skip_setup=True)
    device_entry = register_device(device_registry, config_entry)
    entity_id = register_entity(
        hass,
        SENSOR_DOMAIN,
        "test_name_number_200",
        "number:200-number",
        config_entry,
        device_id=device_entry.id,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entry = entity_registry.async_get(entity_id)
    assert not entry


async def test_rpc_remove_number_virtual_sensor_when_orphaned(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    mock_rpc_device: Mock,
) -> None:
    """Check whether the virtual number sensor will be removed if it has been removed from the device configuration."""
    config_entry = await init_integration(hass, 3, skip_setup=True)
    device_entry = register_device(device_registry, config_entry)
    entity_id = register_entity(
        hass,
        SENSOR_DOMAIN,
        "test_name_number_200",
        "number:200-number",
        config_entry,
        device_id=device_entry.id,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entry = entity_registry.async_get(entity_id)
    assert not entry


@pytest.mark.parametrize(
    ("name", "entity_id", "value", "expected_state"),
    [
        (
            "Virtual enum sensor",
            "sensor.test_name_virtual_enum_sensor",
            "one",
            "Title 1",
        ),
        (None, "sensor.test_name_enum_203", None, STATE_UNKNOWN),
    ],
)
async def test_rpc_device_virtual_enum_sensor(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    name: str | None,
    entity_id: str,
    value: str | None,
    expected_state: str,
) -> None:
    """Test a virtual enum sensor for RPC device."""
    config = deepcopy(mock_rpc_device.config)
    config["enum:203"] = {
        "name": name,
        "options": ["one", "two", "three"],
        "meta": {"ui": {"view": "label", "titles": {"one": "Title 1", "two": None}}},
    }
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["enum:203"] = {"value": value}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 3)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == expected_state
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENUM
    assert state.attributes.get(ATTR_OPTIONS) == ["Title 1", "two", "three"]

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-enum:203-enum"

    monkeypatch.setitem(mock_rpc_device.status["enum:203"], "value", "two")
    mock_rpc_device.mock_update()
    assert hass.states.get(entity_id).state == "two"


async def test_rpc_remove_enum_virtual_sensor_when_mode_dropdown(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test if the virtual enum sensor will be removed if the mode has been changed to a dropdown."""
    config = deepcopy(mock_rpc_device.config)
    config["enum:200"] = {
        "name": None,
        "options": ["option 1", "option 2", "option 3"],
        "meta": {
            "ui": {
                "view": "dropdown",
                "titles": {"option 1": "Title 1", "option 2": None},
            }
        },
    }
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["enum:200"] = {"value": "option 2"}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    config_entry = await init_integration(hass, 3, skip_setup=True)
    device_entry = register_device(device_registry, config_entry)
    entity_id = register_entity(
        hass,
        SENSOR_DOMAIN,
        "test_name_enum_200",
        "enum:200-enum",
        config_entry,
        device_id=device_entry.id,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entry = entity_registry.async_get(entity_id)
    assert not entry


async def test_rpc_remove_enum_virtual_sensor_when_orphaned(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    mock_rpc_device: Mock,
) -> None:
    """Check whether the virtual enum sensor will be removed if it has been removed from the device configuration."""
    config_entry = await init_integration(hass, 3, skip_setup=True)
    device_entry = register_device(device_registry, config_entry)
    entity_id = register_entity(
        hass,
        SENSOR_DOMAIN,
        "test_name_enum_200",
        "enum:200-enum",
        config_entry,
        device_id=device_entry.id,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entry = entity_registry.async_get(entity_id)
    assert not entry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("light_type", ["rgb", "rgbw"])
async def test_rpc_rgbw_sensors(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    light_type: str,
) -> None:
    """Test sensors for RGB/RGBW light."""
    config = deepcopy(mock_rpc_device.config)
    config[f"{light_type}:0"] = {"id": 0}
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status[f"{light_type}:0"] = {
        "temperature": {"tC": 54.3, "tF": 129.7},
        "aenergy": {"total": 45.141},
        "apower": 12.2,
        "current": 0.23,
        "voltage": 12.4,
    }
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 2)

    entity_id = f"sensor.test_name_{light_type}_light_0_power"

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "12.2"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPower.WATT

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == f"123456789ABC-{light_type}:0-power_{light_type}"

    entity_id = f"sensor.test_name_{light_type}_light_0_energy"

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "0.045141"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == f"123456789ABC-{light_type}:0-energy_{light_type}"

    entity_id = f"sensor.test_name_{light_type}_light_0_current"

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "0.23"
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfElectricCurrent.AMPERE
    )

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == f"123456789ABC-{light_type}:0-current_{light_type}"

    entity_id = f"sensor.test_name_{light_type}_light_0_voltage"

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "12.4"
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfElectricPotential.VOLT
    )

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == f"123456789ABC-{light_type}:0-voltage_{light_type}"

    entity_id = f"sensor.test_name_{light_type}_light_0_device_temperature"

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "54.3"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == f"123456789ABC-{light_type}:0-temperature_{light_type}"


async def test_rpc_device_sensor_goes_unavailable_on_disconnect(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test RPC device with sensor goes unavailable on disconnect."""
    await init_integration(hass, 2)
    temp_sensor_state = hass.states.get("sensor.test_name_temperature")
    assert temp_sensor_state is not None
    assert temp_sensor_state.state != STATE_UNAVAILABLE
    monkeypatch.setattr(mock_rpc_device, "connected", False)
    monkeypatch.setattr(mock_rpc_device, "initialized", False)
    mock_rpc_device.mock_disconnected()
    await hass.async_block_till_done()
    temp_sensor_state = hass.states.get("sensor.test_name_temperature")
    assert temp_sensor_state.state == STATE_UNAVAILABLE

    freezer.tick(60)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert "NotInitialized" not in caplog.text

    monkeypatch.setattr(mock_rpc_device, "connected", True)
    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_initialized()
    await hass.async_block_till_done()
    temp_sensor_state = hass.states.get("sensor.test_name_temperature")
    assert temp_sensor_state.state != STATE_UNAVAILABLE
