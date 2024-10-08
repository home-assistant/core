"""Tests for the comfoconnect sensor platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component

COMPONENT = "comfoconnect"
VALID_CONFIG = {
    COMPONENT: {"host": "1.2.3.4"},
    SENSOR_DOMAIN: {
        "platform": COMPONENT,
        "resources": [
            "current_humidity",
            "current_temperature",
            "supply_fan_duty",
            "power_usage",
            "preheater_power_total",
        ],
    },
}


@pytest.fixture
def mock_bridge_discover() -> Generator[MagicMock]:
    """Mock the bridge discover method."""
    with patch("pycomfoconnect.bridge.Bridge.discover") as mock_bridge_discover:
        mock_bridge_discover.return_value[0].uuid.hex.return_value = "00"
        yield mock_bridge_discover


@pytest.fixture
def mock_comfoconnect_command() -> Generator[MagicMock]:
    """Mock the ComfoConnect connect method."""
    with patch(
        "pycomfoconnect.comfoconnect.ComfoConnect._command"
    ) as mock_comfoconnect_command:
        yield mock_comfoconnect_command


@pytest.fixture
async def setup_sensor(
    hass: HomeAssistant,
    mock_bridge_discover: MagicMock,
    mock_comfoconnect_command: MagicMock,
) -> None:
    """Set up demo sensor component."""
    with assert_setup_component(1, SENSOR_DOMAIN):
        await async_setup_component(hass, SENSOR_DOMAIN, VALID_CONFIG)
        await hass.async_block_till_done()


@pytest.mark.usefixtures("setup_sensor")
async def test_sensors(hass: HomeAssistant) -> None:
    """Test the sensors."""
    state = hass.states.get("sensor.comfoairq_inside_humidity")
    assert state is not None
    assert state.name == "ComfoAirQ Inside humidity"
    assert state.attributes.get("unit_of_measurement") == "%"
    assert state.attributes.get("device_class") == "humidity"
    assert state.attributes.get("icon") is None

    state = hass.states.get("sensor.comfoairq_inside_temperature")
    assert state is not None
    assert state.name == "ComfoAirQ Inside temperature"
    assert state.attributes.get("unit_of_measurement") == "°C"
    assert state.attributes.get("device_class") == "temperature"
    assert state.attributes.get("icon") is None

    state = hass.states.get("sensor.comfoairq_supply_fan_duty")
    assert state is not None
    assert state.name == "ComfoAirQ Supply fan duty"
    assert state.attributes.get("unit_of_measurement") == "%"
    assert state.attributes.get("device_class") is None
    assert state.attributes.get("icon") == "mdi:fan-plus"

    state = hass.states.get("sensor.comfoairq_power_usage")
    assert state is not None
    assert state.name == "ComfoAirQ Power usage"
    assert state.attributes.get("unit_of_measurement") == "W"
    assert state.attributes.get("device_class") == "power"
    assert state.attributes.get("icon") is None

    state = hass.states.get("sensor.comfoairq_preheater_energy_total")
    assert state is not None
    assert state.name == "ComfoAirQ Preheater energy total"
    assert state.attributes.get("unit_of_measurement") == "kWh"
    assert state.attributes.get("device_class") == "energy"
    assert state.attributes.get("icon") is None
