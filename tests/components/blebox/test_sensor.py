"""Blebox sensors tests."""

import logging
from unittest.mock import AsyncMock, PropertyMock

import blebox_uniapi
import pytest

from homeassistant.components.blebox.const import CO2_LEVEL, OPEN_STATUS
from homeassistant.components.sensor import ATTR_OPTIONS, SensorDeviceClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import (
    async_setup_config_entry,
    async_setup_entities,
    async_setup_entity,
    mock_feature,
    mock_only_feature,
    setup_product_mock,
)

from tests.common import MockConfigEntry


@pytest.fixture(name="airsensor")
def airsensor_fixture():
    """Return a default AirQuality sensor mock."""
    feature = mock_feature(
        "sensors",
        blebox_uniapi.sensor.AirQuality,
        unique_id="BleBox-airSensor-1afe34db9437-0.air",
        full_name="airSensor-0.air",
        device_class="pm1",
        unit="concentration_of_mp",
        native_value=None,
        index=None,
    )
    type(feature).name = PropertyMock(return_value=None)
    product = feature.product
    type(product).name = PropertyMock(return_value="My air sensor")
    type(product).model = PropertyMock(return_value="airSensor")
    return (feature, "sensor.my_air_sensor_pm1")


@pytest.fixture(name="tempsensor")
def tempsensor_fixture():
    """Return a default Temperature sensor mock."""
    feature = mock_feature(
        "sensors",
        blebox_uniapi.sensor.Temperature,
        unique_id="BleBox-tempSensor-1afe34db9437-0.temperature",
        full_name="tempSensor-0.temperature",
        device_class="temperature",
        unit="celsius",
        current=None,
        native_value=None,
        index=None,
    )
    type(feature).name = PropertyMock(return_value=None)
    product = feature.product
    type(product).name = PropertyMock(return_value="My temperature sensor")
    type(product).model = PropertyMock(return_value="tempSensor")
    return (feature, "sensor.my_temperature_sensor_temperature")


async def test_init(
    tempsensor, hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test sensor default state."""

    _, entity_id = tempsensor
    entry = await async_setup_entity(hass, entity_id)
    assert entry.unique_id == "BleBox-tempSensor-1afe34db9437-0.temperature"

    state = hass.states.get(entity_id)
    assert state.name == "My temperature sensor Temperature"

    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.state == STATE_UNKNOWN

    device = device_registry.async_get(entry.device_id)

    assert device.name == "My temperature sensor"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "tempSensor"
    assert device.sw_version == "1.23"


async def test_update(tempsensor, hass: HomeAssistant) -> None:
    """Test sensor update."""

    feature_mock, entity_id = tempsensor

    feature_mock.native_value = 25.18
    await async_setup_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.state == "25.18"


async def test_update_failure(
    tempsensor,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that update failures cause config entry setup retry."""

    caplog.set_level(logging.ERROR)

    feature_mock, _entity_id = tempsensor
    feature_mock.product.async_update_data = AsyncMock(
        side_effect=blebox_uniapi.error.ClientError
    )

    await async_setup_config_entry(hass, config_entry)

    feature_mock.product.async_update_data.assert_called()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_airsensor_init(
    airsensor, hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test airSensor default state."""

    _, entity_id = airsensor
    entry = await async_setup_entity(hass, entity_id)
    assert entry.unique_id == "BleBox-airSensor-1afe34db9437-0.air"

    state = hass.states.get(entity_id)
    assert state.name == "My air sensor PM1"

    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.PM1
    assert state.state == STATE_UNKNOWN

    device = device_registry.async_get(entry.device_id)

    assert device.name == "My air sensor"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "airSensor"
    assert device.sw_version == "1.23"


async def test_multi_sensor_single_has_no_channel_suffix(
    hass: HomeAssistant,
) -> None:
    """Test that a single indexed sensor shows no channel suffix."""
    feature = mock_feature(
        "sensors",
        blebox_uniapi.sensor.GenericSensor,
        unique_id="BleBox-smartMeter-aabbcc-voltage_0",
        full_name="smartMeter-voltage_0",
        device_class="voltage",
        unit="volt",
        native_value=None,
        sensor_id=0,
        index=0,
    )
    type(feature).name = PropertyMock(return_value=None)
    product = feature.product
    type(product).name = PropertyMock(return_value="My smart meter")
    type(product).model = PropertyMock(return_value="smartMeter")

    await async_setup_entity(hass, "sensor.my_smart_meter_voltage")
    state = hass.states.get("sensor.my_smart_meter_voltage")
    assert state.name == "My smart meter Voltage"


async def test_multi_sensor_multiple_have_channel_suffix(
    hass: HomeAssistant,
) -> None:
    """Test SmartMeter-like device: index=0 (summary) has no suffix, index=1-3 (phases) get phase number suffix."""
    features = [
        mock_only_feature(
            blebox_uniapi.sensor.GenericSensor,
            unique_id=f"BleBox-smartMeter-aabbcc-voltage_{i}",
            full_name=f"smartMeter-voltage_{i}",
            device_class="voltage",
            unit="volt",
            native_value=None,
            sensor_id=i,
            index=i,
        )
        for i in range(4)
    ]

    product = setup_product_mock("sensors", features)
    type(product).name = PropertyMock(return_value="My smart meter")
    type(product).model = PropertyMock(return_value="smartMeter")
    type(product).brand = PropertyMock(return_value="BleBox")
    type(product).firmware_version = PropertyMock(return_value="1.23")
    type(product).unique_id = PropertyMock(return_value="aabbcc112233")

    for feature in features:
        type(feature).product = PropertyMock(return_value=product)
        type(feature).name = PropertyMock(return_value=None)
        feature.async_update = AsyncMock()

    entity_ids = [
        "sensor.my_smart_meter_voltage",
        "sensor.my_smart_meter_voltage_1",
        "sensor.my_smart_meter_voltage_2",
        "sensor.my_smart_meter_voltage_3",
    ]
    await async_setup_entities(hass, entity_ids)

    assert hass.states.get(entity_ids[0]).name == "My smart meter Voltage"
    assert hass.states.get(entity_ids[1]).name == "My smart meter Voltage 1"
    assert hass.states.get(entity_ids[2]).name == "My smart meter Voltage 2"
    assert hass.states.get(entity_ids[3]).name == "My smart meter Voltage 3"


async def test_airsensor_update(airsensor, hass: HomeAssistant) -> None:
    """Test air quality sensor state after update."""

    feature_mock, entity_id = airsensor

    feature_mock.native_value = 49
    await async_setup_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert (
        state.attributes[ATTR_UNIT_OF_MEASUREMENT]
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )

    assert state.state == "49"


@pytest.fixture(name="open_status_sensor")
def open_status_sensor_fixture():
    """Return a default openStatus sensor mock."""
    feature = mock_feature(
        "sensors",
        blebox_uniapi.sensor.GenericSensor,
        unique_id="BleBox-openSensor-1afe34db9437-0.openStatus",
        full_name="openSensor-0.openStatus",
        device_class="openStatus",
        native_value=None,
    )
    type(feature).name = PropertyMock(return_value=None)
    product = feature.product
    type(product).name = PropertyMock(return_value="My open sensor")
    type(product).model = PropertyMock(return_value="openSensor")
    return (feature, "sensor.my_open_sensor_open_status")


async def test_open_status_sensor_init(open_status_sensor, hass: HomeAssistant) -> None:
    """Test openStatus sensor initial state is unknown."""
    _, entity_id = open_status_sensor
    await async_setup_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM
    assert state.attributes[ATTR_OPTIONS] == list(OPEN_STATUS.values())
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("raw_value", "expected_state"),
    [
        pytest.param(0, "open", id="0_open"),
        pytest.param(1, "unclosed_or_unlocked", id="1_unclosed_or_unlocked"),
        pytest.param(2, "ajar", id="2_ajar"),
        pytest.param(3, "closed_but_unlocked", id="3_closed_but_unlocked"),
        pytest.param(4, "closed", id="4_closed"),
    ],
)
async def test_open_status_sensor_value_mapping(
    open_status_sensor,
    hass: HomeAssistant,
    raw_value: int,
    expected_state: str,
) -> None:
    """Test that each raw numeric openStatus value maps to the correct string state."""
    feature_mock, entity_id = open_status_sensor

    feature_mock.native_value = raw_value

    await async_setup_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert state.state == expected_state
    assert state.state in OPEN_STATUS.values()


async def test_open_status_sensor_none_value(
    open_status_sensor, hass: HomeAssistant
) -> None:
    """Test that a None native_value yields an unknown state."""
    feature_mock, entity_id = open_status_sensor

    def set_none():
        feature_mock.native_value = None

    feature_mock.async_update = AsyncMock(side_effect=set_none)
    await async_setup_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert state.state == STATE_UNKNOWN


@pytest.fixture(name="co2_definition_sensor")
def co2_definition_sensor_fixture():
    """Return a default co2Definition sensor mock."""
    feature = mock_feature(
        "sensors",
        blebox_uniapi.sensor.GenericSensor,
        unique_id="BleBox-co2Sensor-1afe34db9437-0.co2Definition",
        full_name="co2Sensor-0.co2Definition",
        device_class="co2Definition",
        native_value=None,
    )
    type(feature).name = PropertyMock(return_value=None)
    product = feature.product
    type(product).name = PropertyMock(return_value="My CO2 sensor")
    type(product).model = PropertyMock(return_value="co2Sensor")
    return (feature, "sensor.my_co2_sensor_carbon_dioxide_level")


async def test_co2_definition_sensor_init(
    co2_definition_sensor, hass: HomeAssistant
) -> None:
    """Test co2Definition sensor initial state is unknown."""
    _, entity_id = co2_definition_sensor
    await async_setup_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM
    assert state.attributes[ATTR_OPTIONS] == list(CO2_LEVEL.values())
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("raw_value", "expected_state"),
    [
        pytest.param(0, "excellent", id="0_excellent"),
        pytest.param(1, "good", id="1_good"),
        pytest.param(2, "acceptable", id="2_acceptable"),
        pytest.param(3, "medium", id="3_medium"),
        pytest.param(4, "poor", id="4_poor"),
        pytest.param(5, "unhealthy", id="5_unhealthy"),
        pytest.param(6, "hazardous", id="6_hazardous"),
    ],
)
async def test_co2_definition_sensor_value_mapping(
    co2_definition_sensor,
    hass: HomeAssistant,
    raw_value: int,
    expected_state: str,
) -> None:
    """Test that each raw co2Definition value maps to the correct string state."""
    feature_mock, entity_id = co2_definition_sensor

    feature_mock.native_value = raw_value
    await async_setup_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert state.state == expected_state
    assert state.state in CO2_LEVEL.values()


async def test_co2_definition_sensor_none_value(
    co2_definition_sensor, hass: HomeAssistant
) -> None:
    """Test that a None native_value yields an unknown state."""
    feature_mock, entity_id = co2_definition_sensor

    def set_none():
        feature_mock.native_value = None

    feature_mock.async_update = AsyncMock(side_effect=set_none)
    await async_setup_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert state.state == STATE_UNKNOWN
