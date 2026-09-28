"""Tests for the Wireless Sensor Tags sensor platform."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, valid_entity_id
from homeassistant.setup import async_setup_component

CONFIG = {
    "wirelesstag": {"username": "foo@bar.com", "password": "secret"},
    "sensor": {
        "platform": "wirelesstag",
        "monitored_conditions": ["temperature", "humidity"],
    },
}


def _mock_tag(name: str) -> MagicMock:
    """Return a mocked wirelesstagpy SensorTag exposing temperature and humidity."""
    tag = MagicMock()
    tag.uuid = "00000000-0000-0000-0000-000000000001"
    tag.tag_id = 1
    tag.tag_manager_mac = "ABCDEF012345"
    tag.name = name
    tag.allowed_sensor_types = ["temperature", "humidity"]
    tag.is_alive = True
    tag.battery_remaining = 0.85
    tag.battery_volts = 3.0
    tag.signal_strength = -60
    tag.is_in_range = True
    tag.power_consumption = 1.5

    def _sensor(sensor_type: str) -> MagicMock:
        sensor = MagicMock()
        if sensor_type == "temperature":
            sensor.value = 21.5
            sensor.unit = UnitOfTemperature.CELSIUS
        else:
            sensor.value = 45.0
            sensor.unit = PERCENTAGE
        return sensor

    tag.sensor.__getitem__.side_effect = _sensor
    return tag


@pytest.mark.parametrize(
    ("tag_name", "expected_entity_id"),
    [
        pytest.param(
            "Bedroom",
            "sensor.wirelesstag_bedroom_temperature",
            id="ascii_name",
        ),
        pytest.param(
            "Küche",
            "sensor.wirelesstag_kuche_temperature",
            id="non_ascii_name",
        ),
    ],
)
async def test_sensor_entity_id_is_valid(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    tag_name: str,
    expected_entity_id: str,
) -> None:
    """Test sensors get a valid entity_id even for non-ASCII tag names.

    A tag named e.g. "Küche" previously produced the invalid entity_id
    "sensor.wirelesstag_küche_temperature", which is rejected by Home
    Assistant's entity ID validation.
    """
    tag = _mock_tag(tag_name)
    with patch("homeassistant.components.wirelesstag.WirelessTags") as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.load_tags.return_value = {tag.uuid: tag}

        assert await async_setup_component(hass, "wirelesstag", CONFIG)
        await hass.async_block_till_done()
        assert await async_setup_component(hass, "sensor", CONFIG)
        await hass.async_block_till_done()

    state = hass.states.get(expected_entity_id)
    assert state is not None
    assert valid_entity_id(state.entity_id)
    assert "sets an invalid entity ID" not in caplog.text
