"""Test the Fressnapf Tracker binary_sensor platform."""

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

from fressnapftracker import Tracker
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.fixture(autouse=True)
async def platforms() -> AsyncGenerator[None]:
    """Return the platforms to be loaded for this test."""
    with patch(
        "homeassistant.components.fressnapf_tracker.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_state_entity_device_snapshots(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary_sensor entity is created correctly."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_auth_client")
async def test_seen_recently_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client_init: MagicMock,
) -> None:
    """Test the seen recently sensor reports a tracker that is asleep."""
    mock_api_client_init.get_tracker.return_value.led_activatable.seen_recently = False

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.fluffy_seen_recently")
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("mock_auth_client")
async def test_seen_recently_not_created_without_led_activatable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client_init: MagicMock,
    mock_tracker_no_position: Tracker,
) -> None:
    """Test the seen recently sensor is not created if the API does not report it."""
    mock_api_client_init.get_tracker.return_value = mock_tracker_no_position

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.fluffy_seen_recently") is None
    assert hass.states.get("binary_sensor.fluffy_charging") is not None
