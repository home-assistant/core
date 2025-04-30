"""Test Roborock Sensors."""

from unittest.mock import patch

import pytest
from roborock import DeviceData, HomeDataDevice
from roborock.roborock_message import RoborockMessage, RoborockMessageProtocol
from roborock.version_1_apis import RoborockMqttClientV1
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .mock_data import CONSUMABLE, STATUS, USER_DATA

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.SENSOR]


async def test_sensors(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensors and check test values are correctly set."""
    assert snapshot == hass.states.async_all("sensor")


async def test_listener_update(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Test that when we receive a mqtt topic, we successfully update the entity."""
    assert hass.states.get("sensor.roborock_s7_maxv_status").state == "charging"
    # Listeners are global based on uuid - so this is okay
    client = RoborockMqttClientV1(
        USER_DATA, DeviceData(device=HomeDataDevice("abc123", "", "", "", ""), model="")
    )
    # Test Status
    with patch("roborock.version_1_apis.AttributeCache.value", STATUS.as_dict()):
        # Symbolizes a mqtt message coming in
        client.on_message_received(
            [
                RoborockMessage(
                    protocol=RoborockMessageProtocol.GENERAL_REQUEST,
                    payload=b'{"t": 1699464794, "dps": {"121": 5}}',
                )
            ]
        )
    # Test consumable
    assert (
        hass.states.get("sensor.roborock_s7_maxv_filter_time_left").state
        == "129.338333333333"
    )
    with patch("roborock.version_1_apis.AttributeCache.value", CONSUMABLE.as_dict()):
        client.on_message_received(
            [
                RoborockMessage(
                    protocol=RoborockMessageProtocol.GENERAL_REQUEST,
                    payload=b'{"t": 1699464794, "dps": {"127": 743}}',
                )
            ]
        )
    await hass.async_block_till_done()
    assert (
        hass.states.get("sensor.roborock_s7_maxv_filter_time_left").state
        == "149.793611111111"
    )
