"""Blebox sensors tests."""

import logging
from unittest.mock import AsyncMock, PropertyMock

import blebox_uniapi
import pytest

from homeassistant.components.sensor import SensorDeviceClass
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
