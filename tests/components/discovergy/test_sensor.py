"""Tests Discovergy sensor component."""
from datetime import timedelta
from unittest.mock import AsyncMock

from pydiscovergy.error import DiscovergyClientError, HTTPError, InvalidLogin
import pytest

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed


@pytest.mark.parametrize(
    (
        "state_name",
        "expected_unique_id",
        "expected_state",
        "expected_unit",
        "expected_device_class",
        "expected_state_class",
    ),
    [
        (
            "sensor.electricity_teststrasse_1_total_consumption",
            "abc123-energy",
            "11934.8699715",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL_INCREASING,
        ),
        (
            "sensor.electricity_teststrasse_1_total_power",
            "abc123-power",
            "531.75",
            UnitOfPower.WATT,
            SensorDeviceClass.POWER,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "sensor.gas_teststrasse_1_total_gas_consumption",
            "def456-volume",
            "21064.8",
            UnitOfVolume.CUBIC_METERS,
            SensorDeviceClass.GAS,
            SensorStateClass.TOTAL_INCREASING,
        ),
    ],
    ids=[
        "electricity total consumption",
        "electricity total power",
        "gas total consumption",
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_name: str,
    expected_unique_id: str,
    expected_state: str,
    expected_unit: str,
    expected_device_class: SensorDeviceClass,
    expected_state_class: SensorStateClass,
) -> None:
    """Test sensor setup and update."""

    entry = entity_registry.async_get(state_name)
    assert entry
    assert entry.unique_id == expected_unique_id

    state = hass.states.get(state_name)
    assert state.state == expected_state
    assert state.attributes.get(ATTR_DEVICE_CLASS) == expected_device_class
    assert state.attributes.get(ATTR_STATE_CLASS) == expected_state_class
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == expected_unit


@pytest.mark.parametrize(
    "error",
    [
        InvalidLogin,
        HTTPError,
        DiscovergyClientError,
        Exception,
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_sensor_update_fail(
    hass: HomeAssistant,
    discovergy: AsyncMock,
    error: Exception,
) -> None:
    """Test sensor errors."""
    discovergy.meter_last_reading.side_effect = error

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=300))
    await hass.async_block_till_done()

    state = hass.states.get("sensor.electricity_teststrasse_1_total_consumption")
    assert state
    assert state.state == "unavailable"
