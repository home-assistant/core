"""Tests for asyncua sensors."""
import unittest
from unittest.mock import MagicMock

import pytest

from homeassistant.components.asyncua.const import DOMAIN
from homeassistant.components.asyncua.sensor import AsyncuaSensor, async_setup_platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryError,
)

from tests.common import MockConfigEntry


async def test_setup_minimal_hub_not_found(
    setup_asyncua_coordinator,
    hass: HomeAssistant,
) -> None:
    """Ensure error is raised if asyncua hub is not configured."""
    config = {
        "platform": "asyncua",
        "nodes": [
            {
                "name": "mock_sensor_01",
                "unique_id": "mock_sensor_01",
                "device_class": "temperature",
                "hub": "mock-missing-hub",
                "nodeid": "99",
            },
        ],
    }
    with pytest.raises(ConfigEntryError):
        await async_setup_platform(
            hass=hass, config=config, async_add_entities=MagicMock()
        )
        await hass.async_block_till_done()
        state = hass.states.get("mock_sensor_01")
        assert state is None


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("config", "domain", "entity_id", "name"),
    [
        (
            {
                "sensor": {
                    "platform": "asyncua",
                    "nodes": [
                        {
                            "name": "mock_sensor_01",
                            "unique_id": "mock_sensor_01",
                            "device_class": "temperature",
                            "hub": "mock-hub",
                            "nodeid": "99",
                        }
                    ],
                },
            },
            "sensor",
            "sensor.mock_sensor_01",
            "mock_sensor_01",
        ),
    ],
)
async def test_setup_minimal(
    setup_asyncua_coordinator,
    hass: HomeAssistant,
    start_ha,
    entity_id,
    name,
) -> None:
    """Test the setup."""
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == name
    assert state.state == "unknown"

    hass.states.async_set(
        entity_id="sensor.mock_sensor_01",
        new_state=368,
        attributes={
            "state_class": "measurement",
            "device_class": "temperature",
            "friendly_name": "mock_sensor_01",
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "368"


class TestAsyncuaSensor(unittest.TestCase):
    """Test for asyncua sensor."""

    def setUp(self) -> None:
        """Set up coordinator and binary_sensor."""
        self.mock_asyncua_coordinator = MockConfigEntry(
            domain=DOMAIN,
            data={"mock-asyncua-sensor": 99},
            title="Mock-Asyncua-Coordinator",
        )
        self.mock_sensor = AsyncuaSensor(
            coordinator=self.mock_asyncua_coordinator,
            name="mock-asyncua-sensor",
            hub="mock-hub",
            node_id="ns=mock;s=mock",
            unique_id="mock-asyncua-sensor",
            device_class=None,
        )

    def tearDown(self) -> None:
        """Remove coordinator and sensor."""
        del self.mock_asyncua_coordinator
        del self.mock_sensor

    def test_get_node_id(self) -> None:
        """Test to get sensor node_id."""
        assert self.mock_sensor.node_id == "ns=mock;s=mock"

    def test_sensor_without_unique_id(self):
        """Test default unique_id if not provided in configuration.yaml file."""
        mock_sensor_without_unique_id = AsyncuaSensor(
            coordinator=self.mock_asyncua_coordinator,
            name="mock-sensor-without-unique-id",
            hub="mock-hub",
            node_id="ns=mock;s=mock",
            device_class=None,
        )
        expected = "asyncua.mock-hub.ns=mock;s=mock"
        self.assertEqual(expected, mock_sensor_without_unique_id.unique_id)

    def test_parse_coordinator_data_invalid_attr_name(self):
        """Test default unique_id if not provided in configuration.yaml file."""
        mock_sensor_invalid_attr_name = AsyncuaSensor(
            coordinator=self.mock_asyncua_coordinator,
            name="mock-asyncua-sensor-invalid-name",
            hub="mock-hub",
            node_id="ns=mock;s=mock",
            unique_id="mock-asyncua-sensor-invalid-name",
            device_class=None,
        )
        result = mock_sensor_invalid_attr_name._parse_coordinator_data(
            coordinator_data=mock_sensor_invalid_attr_name.coordinator.data
        )
        self.assertIsNone(result)

    def test_parse_coordinator_data_pass(self):
        """Test the event."""
        expected = 99
        result = self.mock_sensor._parse_coordinator_data(
            coordinator_data=self.mock_sensor.coordinator.data
        )
        self.assertEqual(expected, result)
