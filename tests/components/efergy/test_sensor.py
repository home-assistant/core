"""The tests for Efergy sensor platform."""

from datetime import timedelta

import pytest

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from . import MULTI_SENSOR_TOKEN, mock_responses, setup_platform

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


async def test_sensor_readings(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test for successfully setting up the Efergy platform."""
    await setup_platform(hass, aioclient_mock, SENSOR_DOMAIN)

    state = hass.states.get("sensor.efergy_power_usage")
    assert state.state == "1580"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPower.WATT
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    state = hass.states.get("sensor.efergy_energy_budget")
    assert state.state == "ok"
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    state = hass.states.get("sensor.efergy_daily_consumption")
    assert state.state == "38.21"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL_INCREASING
    state = hass.states.get("sensor.efergy_weekly_consumption")
    assert state.state == "267.47"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL_INCREASING
    state = hass.states.get("sensor.efergy_monthly_consumption")
    assert state.state == "1069.88"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL_INCREASING
    state = hass.states.get("sensor.efergy_yearly_consumption")
    assert state.state == "13373.50"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL_INCREASING
    state = hass.states.get("sensor.efergy_daily_energy_cost")
    assert state.state == "5.27"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.MONETARY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "EUR"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL_INCREASING
    state = hass.states.get("sensor.efergy_weekly_energy_cost")
    assert state.state == "36.89"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.MONETARY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "EUR"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL_INCREASING
    state = hass.states.get("sensor.efergy_monthly_energy_cost")
    assert state.state == "147.56"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.MONETARY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "EUR"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL_INCREASING
    state = hass.states.get("sensor.efergy_yearly_energy_cost")
    assert state.state == "1844.50"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.MONETARY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "EUR"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL_INCREASING
    state = hass.states.get("sensor.efergy_power_usage_728386")
    assert state.state == "1628"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPower.WATT
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT


async def test_multi_sensor_readings(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test for multiple sensors in one household."""
    await setup_platform(hass, aioclient_mock, SENSOR_DOMAIN, MULTI_SENSOR_TOKEN)
    state = hass.states.get("sensor.efergy_power_usage_728386")
    assert state.state == "218"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPower.WATT
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    state = hass.states.get("sensor.efergy_power_usage_0")
    assert state.state == "1808"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPower.WATT
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    state = hass.states.get("sensor.efergy_power_usage_728387")
    assert state.state == "312"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPower.WATT
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT


async def test_failed_update_and_reconnection(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test failed update and reconnection."""
    await setup_platform(hass, aioclient_mock, SENSOR_DOMAIN)
    assert hass.states.get("sensor.efergy_power_usage").state == "1580"
    aioclient_mock.clear_requests()
    await mock_responses(hass, aioclient_mock, error=True)
    next_update = dt_util.utcnow() + timedelta(seconds=30)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("sensor.efergy_power_usage").state == STATE_UNAVAILABLE
    aioclient_mock.clear_requests()
    await mock_responses(hass, aioclient_mock)
    next_update = dt_util.utcnow() + timedelta(seconds=30)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("sensor.efergy_power_usage").state == "1580"
