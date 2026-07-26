"""Tests for the Wireless Sensor Tags switch platform."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

UUID = "00000000-0000-0000-0000-000000000003"
TAG_ID = 3
MAC = "ABCDEF012345"

CONFIG = {
    "wirelesstag": {"username": "foo@bar.com", "password": "secret"},
    "switch": {"platform": "wirelesstag", "monitored_conditions": ["moisture"]},
}


def _mock_water_tag() -> MagicMock:
    """Return a mocked water tag that exposes the moisture monitoring type."""
    tag = MagicMock()
    tag.uuid = UUID
    tag.tag_id = TAG_ID
    tag.tag_manager_mac = MAC
    tag.name = "Basement"
    tag.is_alive = True
    tag.allowed_monitoring_types = ["temperature", "moisture"]
    tag.is_moisture_sensor_armed = False
    tag.battery_remaining = 0.9
    tag.battery_volts = 3.0
    tag.signal_strength = -55
    tag.is_in_range = True
    tag.power_consumption = 1.0
    return tag


@pytest.mark.parametrize(
    ("service", "expected_method"),
    [
        (SERVICE_TURN_ON, "arm_humidity"),
        (SERVICE_TURN_OFF, "disarm_humidity"),
    ],
)
async def test_moisture_switch_uses_cap_sensor_endpoint(
    hass: HomeAssistant,
    service: str,
    expected_method: str,
) -> None:
    """Test the moisture switch arms/disarms via the cap sensor endpoint.

    Water tags expose the capacitive sensor as "moisture", but wirelesstagpy
    only provides arm_humidity/disarm_humidity (ArmCapSensor). The switch must
    map moisture to those endpoints instead of crashing on a missing
    arm_moisture/disarm_moisture method.
    """
    tag = _mock_water_tag()
    # autospec ensures the (non-existent) arm_moisture/disarm_moisture raise
    # AttributeError, reproducing the crash without the fix.
    with patch(
        "homeassistant.components.wirelesstag.WirelessTags", autospec=True
    ) as mock_class:
        mock_api = mock_class.return_value
        mock_api.load_tags.return_value = {tag.uuid: tag}

        assert await async_setup_component(hass, "wirelesstag", CONFIG)
        await hass.async_block_till_done()
        assert await async_setup_component(hass, "switch", CONFIG)
        await hass.async_block_till_done()

        entity_id = er.async_get(hass).async_get_entity_id(
            "switch", "wirelesstag", f"{UUID}_moisture"
        )
        assert entity_id is not None

        await hass.services.async_call(
            "switch", service, {"entity_id": entity_id}, blocking=True
        )
        await hass.async_block_till_done()

    getattr(mock_api, expected_method).assert_called_once_with(TAG_ID, MAC)
