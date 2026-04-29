"""Blebox sensors tests."""

from datetime import timedelta
import logging
from unittest.mock import AsyncMock, PropertyMock, patch

import blebox_uniapi
import pytest

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    STATE_UNKNOWN,
    UnitOfEnergy,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import DATA_DOMAIN_PLATFORM_ENTITIES
from homeassistant.util.dt import utcnow

from .conftest import async_setup_entities, async_setup_entity, mock_feature

from tests.common import mock_restore_cache_with_extra_data


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
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My air sensor")
    type(product).model = PropertyMock(return_value="airSensor")
    return (feature, "sensor.my_air_sensor_airsensor_0_air")


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
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My temperature sensor")
    type(product).model = PropertyMock(return_value="tempSensor")
    return (feature, "sensor.my_temperature_sensor_tempsensor_0_temperature")


@pytest.fixture(name="switchbox")
def switchbox_fixture():
    """Return a switchBox activePower sensor mock (produces both power + energy entities)."""
    feature = mock_feature(
        "sensors",
        blebox_uniapi.sensor.BaseSensor,
        unique_id="BleBox-switchBox-1afe34db9437-0.activePower",
        full_name="switchBox-0.activePower",
        device_class="activePower",
        unit="W",
        native_value=None,
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My switch box")
    type(product).model = PropertyMock(return_value="switchBox")
    type(product).type = PropertyMock(return_value="switchBox")
    power_entity_id = "sensor.my_switch_box_switchbox_0_activepower"
    energy_entity_id = "sensor.my_switch_box_switchbox_totalenergy"
    return (feature, power_entity_id, energy_entity_id)


async def test_init(
    tempsensor, hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test sensor default state."""

    _, entity_id = tempsensor
    entry = await async_setup_entity(hass, entity_id)
    assert entry.unique_id == "BleBox-tempSensor-1afe34db9437-0.temperature"

    state = hass.states.get(entity_id)
    assert state.name == "My temperature sensor tempSensor-0.temperature"

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

    def initial_update():
        feature_mock.native_value = 25.18

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.state == "25.18"


async def test_update_failure(
    tempsensor, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that update failures are logged."""

    caplog.set_level(logging.ERROR)

    feature_mock, entity_id = tempsensor
    feature_mock.async_update = AsyncMock(side_effect=blebox_uniapi.error.ClientError)
    await async_setup_entity(hass, entity_id)

    assert f"Updating '{feature_mock.full_name}' failed: " in caplog.text


async def test_airsensor_init(
    airsensor, hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test airSensor default state."""

    _, entity_id = airsensor
    entry = await async_setup_entity(hass, entity_id)
    assert entry.unique_id == "BleBox-airSensor-1afe34db9437-0.air"

    state = hass.states.get(entity_id)
    assert state.name == "My air sensor airSensor-0.air"

    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.PM1
    assert state.state == STATE_UNKNOWN

    device = device_registry.async_get(entry.device_id)

    assert device.name == "My air sensor"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "airSensor"
    assert device.sw_version == "1.23"


async def test_airsensor_update(airsensor, hass: HomeAssistant) -> None:
    """Test air quality sensor state after update."""

    feature_mock, entity_id = airsensor

    def initial_update():
        feature_mock.native_value = 49

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert (
        state.attributes[ATTR_UNIT_OF_MEASUREMENT]
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )

    assert state.state == "49"


async def test_power_consumption_state_class(hass: HomeAssistant) -> None:
    """Test that powerConsumption sensor has MEASUREMENT state class."""
    feature = mock_feature(
        "sensors",
        blebox_uniapi.sensor.BaseSensor,
        unique_id="BleBox-switchBox-1afe34db9437-0.powerConsumption",
        full_name="switchBox-0.powerConsumption",
        device_class="powerConsumption",
        unit="kWh",
        native_value=None,
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My switch box")
    type(product).model = PropertyMock(return_value="switchBox")

    entity_id = "sensor.my_switch_box_switchbox_0_powerconsumption"
    entry = await async_setup_entity(hass, entity_id)
    assert entry is not None

    state = hass.states.get(entity_id)
    assert state.attributes.get("state_class") == SensorStateClass.MEASUREMENT


async def test_energy_sensor_init(switchbox, hass: HomeAssistant) -> None:
    """Test energy sensor initial state is 0.0 with TOTAL state class."""
    feature_mock, power_entity_id, energy_entity_id = switchbox

    feature_mock.native_value = 0.0
    await async_setup_entities(hass, [power_entity_id, energy_entity_id])

    state = hass.states.get(energy_entity_id)
    assert state is not None
    assert state.state == "0.0"
    assert state.attributes.get("state_class") == SensorStateClass.TOTAL
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR


async def test_energy_sensor_first_update_no_accumulation(
    switchbox, hass: HomeAssistant
) -> None:
    """Test that the first update only seeds the baseline without accumulating energy."""
    feature_mock, power_entity_id, energy_entity_id = switchbox

    t0 = utcnow()

    def initial_update():
        feature_mock.native_value = 1000.0

    feature_mock.async_update = AsyncMock(side_effect=initial_update)

    with patch(
        "homeassistant.components.blebox.sensor.dt_util.utcnow", return_value=t0
    ):
        await async_setup_entities(hass, [power_entity_id, energy_entity_id])

    state = hass.states.get(energy_entity_id)
    assert state.state == "0.0"


async def test_energy_sensor_accumulates_after_second_update(
    switchbox, hass: HomeAssistant
) -> None:
    """Test energy accumulation via trapezoidal rule after two consecutive polls 5s apart."""
    feature_mock, power_entity_id, energy_entity_id = switchbox

    t0 = utcnow()
    t1 = t0 + timedelta(seconds=5)

    feature_mock.native_value = 1000.0
    feature_mock.async_update = AsyncMock()

    with patch(
        "homeassistant.components.blebox.sensor.dt_util.utcnow", return_value=t0
    ):
        await async_setup_entities(hass, [power_entity_id, energy_entity_id])

    entities = hass.data[DATA_DOMAIN_PLATFORM_ENTITIES][("sensor", "blebox")]
    energy_entity = entities[energy_entity_id]

    with patch(
        "homeassistant.components.blebox.sensor.dt_util.utcnow", return_value=t1
    ):
        await energy_entity.async_update()
        energy_entity.async_write_ha_state()

    state = hass.states.get(energy_entity_id)
    expected = (1000 + 1000) / 2 * 5 / 3_600_000
    assert float(state.state) == pytest.approx(expected, rel=1e-4)


async def test_energy_sensor_skips_long_gap(switchbox, hass: HomeAssistant) -> None:
    """Test that an elapsed gap > 30 s resets context without accumulating."""
    feature_mock, power_entity_id, energy_entity_id = switchbox

    t0 = utcnow()
    t_gap = t0 + timedelta(seconds=31)

    feature_mock.native_value = 1000.0
    feature_mock.async_update = AsyncMock()

    with patch(
        "homeassistant.components.blebox.sensor.dt_util.utcnow", return_value=t0
    ):
        await async_setup_entities(hass, [power_entity_id, energy_entity_id])

    entities = hass.data[DATA_DOMAIN_PLATFORM_ENTITIES][("sensor", "blebox")]
    energy_entity = entities[energy_entity_id]

    with patch(
        "homeassistant.components.blebox.sensor.dt_util.utcnow", return_value=t_gap
    ):
        await energy_entity.async_update()
        energy_entity.async_write_ha_state()

    state = hass.states.get(energy_entity_id)
    assert state.state == "0.0"


async def test_energy_sensor_restore(switchbox, hass: HomeAssistant) -> None:
    """Test that accumulated energy is restored after a restart."""
    feature_mock, power_entity_id, energy_entity_id = switchbox

    feature_mock.native_value = 500.0
    feature_mock.async_update = AsyncMock()

    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(energy_entity_id, "1.5"),
                {
                    "native_value": "1.5",
                    "native_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                },
            )
        ],
    )

    t0 = utcnow()
    t1 = t0 + timedelta(seconds=5)

    with patch(
        "homeassistant.components.blebox.sensor.dt_util.utcnow", return_value=t0
    ):
        await async_setup_entities(hass, [power_entity_id, energy_entity_id])

    state = hass.states.get(energy_entity_id)
    assert float(state.state) == pytest.approx(1.5)

    entities = hass.data[DATA_DOMAIN_PLATFORM_ENTITIES][("sensor", "blebox")]
    energy_entity = entities[energy_entity_id]

    with patch(
        "homeassistant.components.blebox.sensor.dt_util.utcnow", return_value=t1
    ):
        await energy_entity.async_update()
        energy_entity.async_write_ha_state()

    state = hass.states.get(energy_entity_id)
    delta = (500 + 500) / 2 * 5 / 3_600_000
    assert float(state.state) == pytest.approx(1.5 + delta, rel=1e-4)
