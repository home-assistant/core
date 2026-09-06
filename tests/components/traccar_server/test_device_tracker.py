"""Test the Traccar Server device tracker."""

from unittest.mock import AsyncMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import get_subscription_callback
from .common import setup_integration

from tests.common import MockConfigEntry


async def test_update_data_happy_path(
    hass: HomeAssistant,
    mock_traccar_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Devices, positions, and geofences merged by the coordinator reach the device tracker."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("device_tracker.x_wing")
    assert state is not None
    assert state.attributes["latitude"] == 52.0
    assert state.attributes["longitude"] == 25.0
    assert state.attributes["gps_accuracy"] == 3.5
    # accuracy (3.5) is below max_accuracy (5.0), so the custom attribute
    # should be included rather than filtered out.
    assert state.attributes["custom_attr_1"] == "custom_attr_1_value"


async def test_handle_subscription_data_updates_known_device(
    hass: HomeAssistant,
    mock_traccar_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A subscription update for a known device updates its device tracker state."""
    await setup_integration(hass, mock_config_entry)
    subscription_callback = get_subscription_callback(mock_traccar_api_client)

    updated_position = {
        "id": 0,
        "deviceId": 0,
        "latitude": 60.0,
        "longitude": 30.0,
        "accuracy": 3.5,
        "address": "Mos Eisley",
        "attributes": {"custom_attr_1": "custom_attr_1_value"},
    }

    await subscription_callback(
        {"devices": None, "events": None, "positions": [updated_position]}
    )
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.x_wing")
    assert state.attributes["latitude"] == 60.0
    assert state.attributes["longitude"] == 30.0


async def test_handle_subscription_data_ignores_unknown_device(
    hass: HomeAssistant,
    mock_traccar_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Subscription data for a device we haven't seen via polling is ignored."""
    await setup_integration(hass, mock_config_entry)
    subscription_callback = get_subscription_callback(mock_traccar_api_client)

    state_before = hass.states.get("device_tracker.x_wing")

    unknown_position = {
        "id": 999,
        "deviceId": 999,
        "latitude": 60.0,
        "longitude": 30.0,
        "accuracy": 3.5,
        "address": "Mos Eisley",
        "attributes": {},
    }

    # Should not raise, and should not touch the known device's state.
    await subscription_callback(
        {"devices": None, "events": None, "positions": [unknown_position]}
    )
    await hass.async_block_till_done()

    state_after = hass.states.get("device_tracker.x_wing")
    assert state_after.state == state_before.state
    assert state_after.attributes == state_before.attributes
    assert hass.states.get("device_tracker.unknown_999") is None


async def test_handle_subscription_data_filters_low_accuracy_position(
    hass: HomeAssistant,
    mock_traccar_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A position update that fails the accuracy filter is skipped."""
    await setup_integration(hass, mock_config_entry)
    subscription_callback = get_subscription_callback(mock_traccar_api_client)

    original_latitude = hass.states.get("device_tracker.x_wing").attributes["latitude"]

    poor_accuracy_position = {
        "id": 0,
        "deviceId": 0,
        "latitude": 60.0,
        "longitude": 30.0,
        # max_accuracy for this config entry is 5.0.
        "accuracy": 999.0,
        "address": "Should not be applied",
        "attributes": {"custom_attr_1": "custom_attr_1_value"},
    }

    await subscription_callback(
        {"devices": None, "events": None, "positions": [poor_accuracy_position]}
    )
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.x_wing")
    assert state.attributes["latitude"] == original_latitude
