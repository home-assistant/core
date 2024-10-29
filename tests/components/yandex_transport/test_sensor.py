"""Tests for the yandex transport platform."""

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components import sensor
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import assert_setup_component, load_fixture

BUS_REPLY = json.loads(load_fixture("bus_reply.json", "yandex_transport"))
SUBURBAN_TRAIN_REPLY = json.loads(
    load_fixture("suburban_reply.json", "yandex_transport")
)


@pytest.fixture
def mock_requester_bus():
    """Create a mock for YandexMapsRequester."""
    with patch(
        "homeassistant.components.yandex_transport.sensor.YandexMapsRequester"
    ) as requester:
        instance = requester.return_value
        instance.set_new_session = AsyncMock()
        instance.get_stop_info = AsyncMock(return_value=BUS_REPLY)
        yield instance


@pytest.fixture
def mock_requester_suburban_train():
    """Create a mock for YandexMapsRequester."""
    with patch(
        "homeassistant.components.yandex_transport.sensor.YandexMapsRequester"
    ) as requester:
        instance = requester.return_value
        instance.set_new_session = AsyncMock()
        instance.get_stop_info = AsyncMock(return_value=SUBURBAN_TRAIN_REPLY)
        yield instance


STOP_ID = "stop__9639579"
ROUTES = ["194", "т36", "т47", "м10"]
NAME = "test_name"
TEST_BUS_CONFIG = {
    "sensor": {
        "platform": "yandex_transport",
        "stop_id": "stop__9639579",
        "routes": ROUTES,
        "name": NAME,
    }
}
TEST_SUBURBAN_CONFIG = {
    "sensor": {
        "platform": "yandex_transport",
        "stop_id": "station__lh_9876336",
        "name": NAME,
    }
}

FILTERED_ATTRS = {
    "т36": ["18:25", "18:42", "18:46"],
    "т47": ["18:35", "18:37", "18:40", "18:42"],
    "м10": ["18:20", "18:27", "18:29", "18:41", "18:43"],
    "stop_name": "7-й автобусный парк",
    "attribution": "Data provided by maps.yandex.ru",
}

BUS_RESULT_STATE = dt_util.utc_from_timestamp(1583421540).isoformat(timespec="seconds")
SUBURBAN_RESULT_STATE = dt_util.utc_from_timestamp(1634984640).isoformat(
    timespec="seconds"
)


async def assert_setup_sensor(
    hass: HomeAssistant, config: dict[str, Any], count: int = 1
) -> None:
    """Set up the sensor and assert it's been created."""
    with assert_setup_component(count):
        assert await async_setup_component(hass, sensor.DOMAIN, config)
        await hass.async_block_till_done()


async def test_setup_platform_valid_config(
    hass: HomeAssistant, mock_requester_bus
) -> None:
    """Test that sensor is set up properly with valid config."""
    await assert_setup_sensor(hass, TEST_BUS_CONFIG)


async def test_setup_platform_invalid_config(
    hass: HomeAssistant, mock_requester_bus
) -> None:
    """Check an invalid configuration."""
    await assert_setup_sensor(
        hass, {"sensor": {"platform": "yandex_transport", "stopid": 1234}}, count=0
    )


async def test_name(hass: HomeAssistant, mock_requester_bus) -> None:
    """Return the name if set in the configuration."""
    await assert_setup_sensor(hass, TEST_BUS_CONFIG)
    state = hass.states.get("sensor.test_name")
    assert state.name == TEST_BUS_CONFIG["sensor"][CONF_NAME]


async def test_state(hass: HomeAssistant, mock_requester_bus) -> None:
    """Return the contents of _state."""
    await assert_setup_sensor(hass, TEST_BUS_CONFIG)
    state = hass.states.get("sensor.test_name")
    assert state.state == BUS_RESULT_STATE


async def test_filtered_attributes(hass: HomeAssistant, mock_requester_bus) -> None:
    """Return the contents of attributes."""
    await assert_setup_sensor(hass, TEST_BUS_CONFIG)
    state = hass.states.get("sensor.test_name")
    state_attrs = {key: state.attributes[key] for key in FILTERED_ATTRS}
    assert state_attrs == FILTERED_ATTRS


async def test_suburban_trains(
    hass: HomeAssistant, mock_requester_suburban_train
) -> None:
    """Return the contents of _state for suburban."""
    await assert_setup_sensor(hass, TEST_SUBURBAN_CONFIG)
    state = hass.states.get("sensor.test_name")
    assert state.state == SUBURBAN_RESULT_STATE
