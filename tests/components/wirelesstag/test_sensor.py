"""Tests for the Wireless Sensor Tags sensor platform."""

from unittest.mock import MagicMock, patch

from homeassistant.const import STATE_UNAVAILABLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.setup import async_setup_component

UUID = "00000000-0000-0000-0000-000000000001"
ENTITY_ID = "sensor.wirelesstag_bedroom_temperature"

CONFIG = {
    "wirelesstag": {"username": "foo@bar.com", "password": "secret"},
    "sensor": {
        "platform": "wirelesstag",
        "monitored_conditions": ["temperature"],
    },
}


def _mock_tag() -> MagicMock:
    """Return a mocked tag exposing a temperature sensor."""
    tag = MagicMock()
    tag.uuid = UUID
    tag.tag_id = 1
    tag.tag_manager_mac = "ABCDEF012345"
    tag.name = "Bedroom"
    tag.allowed_sensor_types = ["temperature"]
    tag.is_alive = True
    tag.battery_remaining = 0.85
    tag.battery_volts = 3.0
    tag.signal_strength = -60
    tag.is_in_range = True
    tag.power_consumption = 1.5

    def _sensor(sensor_type: str) -> MagicMock:
        sensor = MagicMock()
        sensor.value = 21.5
        sensor.unit = UnitOfTemperature.CELSIUS
        return sensor

    tag.sensor.__getitem__.side_effect = _sensor
    return tag


async def test_update_handles_tag_missing_from_reload(hass: HomeAssistant) -> None:
    """Test an update where the tag is no longer returned is handled gracefully.

    If a reload no longer contains the entity's tag, the update must mark the
    entity unavailable instead of raising a KeyError or keeping a stale value.
    """
    tag = _mock_tag()
    with patch("homeassistant.components.wirelesstag.WirelessTags") as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.load_tags.return_value = {tag.uuid: tag}

        assert await async_setup_component(hass, "wirelesstag", CONFIG)
        await hass.async_block_till_done()
        assert await async_setup_component(hass, "sensor", CONFIG)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == "21.5"

        # The tag is no longer returned by a reload.
        mock_api.load_tags.return_value = {}
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()

        assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

        # The tag is returned again and the entity recovers.
        mock_api.load_tags.return_value = {tag.uuid: tag}
        await async_update_entity(hass, ENTITY_ID)
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == "21.5"
