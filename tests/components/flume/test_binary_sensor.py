"""Test the flume binary sensors."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import LOW_BATTERY_NOTIFICATION, NOTIFICATION

from tests.common import MockConfigEntry, snapshot_platform

LOW_BATTERY_ENTITY_ID = "binary_sensor.flume_sensor_sensor_location_battery"


@pytest.fixture(autouse=True)
def platforms_fixture():
    """Return the platforms to be loaded for this test."""
    with patch("homeassistant.components.flume.PLATFORMS", [Platform.BINARY_SENSOR]):
        yield


@pytest.mark.usefixtures("access_token", "device_list", "notifications_list")
async def test_binary_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensors."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("battery_level", "expected_state"),
    [
        ("low", STATE_ON),
        ("medium", STATE_OFF),
        ("high", STATE_OFF),
        # An unrecognized or absent level must not be reported as a healthy
        # battery.
        ("unexpected", STATE_UNKNOWN),
        (None, STATE_UNKNOWN),
    ],
)
@pytest.mark.usefixtures("access_token", "device_list", "notifications_list")
async def test_low_battery_from_device_list(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    expected_state: str,
) -> None:
    """Test the battery state is derived from the reported battery level."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(LOW_BATTERY_ENTITY_ID)
    assert state
    assert state.state == expected_state


@pytest.mark.parametrize("battery_level", ["high"])
@pytest.mark.parametrize("notifications", [[NOTIFICATION, LOW_BATTERY_NOTIFICATION]])
@pytest.mark.usefixtures("access_token", "device_list", "notifications_list")
async def test_low_battery_ignores_stale_notification(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test a stale low battery notification does not mark the battery low.

    Flume keeps low battery notifications active until they are deleted in the
    app, so they cannot be used to determine the current battery state.
    """
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(LOW_BATTERY_ENTITY_ID)
    assert state
    assert state.state == STATE_OFF
