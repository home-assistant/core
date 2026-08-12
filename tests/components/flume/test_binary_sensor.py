"""Tests for Flume binary sensors."""

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest
from requests_mock.mocker import Mocker
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.flume.const import DOMAIN
from homeassistant.const import STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import NOTIFICATIONS_URL, SENSOR_DEVICE, USER_ID

from tests.common import MockConfigEntry, snapshot_platform


def active_notification(event_rule_name: str) -> dict[str, Any]:
    """Build a read but uncleared notification for the sensor device."""
    return {
        "id": 222222,
        "device_id": SENSOR_DEVICE["id"],
        "user_id": USER_ID,
        "type": 16,
        "message": f"{event_rule_name} triggered at Home.",
        "read": True,
        "extra": {"event_rule_name": event_rule_name},
    }


@pytest.fixture(autouse=True)
def platforms_fixture() -> Generator[None]:
    """Set up only the binary sensor platform."""
    with patch("homeassistant.components.flume.PLATFORMS", [Platform.BINARY_SENSOR]):
        yield


@pytest.mark.usefixtures("access_token", "device_list")
async def test_binary_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    requests_mock: Mocker,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensors with no notification outstanding."""
    requests_mock.get(NOTIFICATIONS_URL, json={"data": []})

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.usefixtures("access_token", "device_list")
@pytest.mark.parametrize(
    ("event_rule_name", "unique_id"),
    [
        pytest.param("Flume Smart Leak Alert", "leak_1234", id="leak"),
        pytest.param("High Flow Alert", "flow_1234", id="high_flow"),
        pytest.param("Low Battery", "low_battery_1234", id="low_battery"),
    ],
)
async def test_notification_binary_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    requests_mock: Mocker,
    event_rule_name: str,
    unique_id: str,
) -> None:
    """Test each sensor is on while its notification is in the list.

    A notification stays in the list until it is deleted in the Flume app.
    """
    requests_mock.get(
        NOTIFICATIONS_URL,
        json={"data": [active_notification(event_rule_name)]},
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        Platform.BINARY_SENSOR, DOMAIN, unique_id
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON
