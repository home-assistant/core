"""Test the ISEO Argo BLE sensor entities."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from homeassistant.components.iseo_argo_ble.coordinator import entry_message, event_name
from homeassistant.core import HomeAssistant

from iseo_argo_ble import LogEntry

from tests.common import MockConfigEntry

from .conftest import mock_config_entry, mock_derive_private_key, mock_iseo_client  # noqa: F401


async def _setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.iseo_argo_ble.async_ble_device_from_address",
        return_value=MagicMock(),
    ), patch(
        "homeassistant.components.iseo_argo_ble.coordinator.async_ble_device_from_address",
        return_value=MagicMock(),
    ), patch(
        "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
        return_value=MagicMock(),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


async def test_sensors_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test that sensor entities are created on setup."""
    await _setup_integration(
        hass, mock_config_entry, mock_iseo_client, mock_derive_private_key
    )

    all_sensors = [s for s in hass.states.async_all() if s.domain == "sensor"]
    # Two sensors should be created: last_event and battery
    assert len(all_sensors) == 2


async def test_battery_sensor_initial_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test battery sensor returns None when no log data available."""
    await _setup_integration(
        hass, mock_config_entry, mock_iseo_client, mock_derive_private_key
    )

    all_sensors = [s for s in hass.states.async_all() if s.domain == "sensor"]
    assert len(all_sensors) == 2
    # No log entries yet → unknown state for both sensors
    assert all(s.state in ("unknown", "unavailable") for s in all_sensors)


def test_event_name_known_code() -> None:
    """Test event_name returns correct string for known codes."""
    assert event_name(8) == "Opened"
    assert event_name(19) == "Closed"
    assert event_name(15) == "User added"


def test_event_name_unknown_code() -> None:
    """Test event_name returns generic string for unknown codes."""
    assert event_name(999) == "Event 999"


def test_entry_message_with_user_dir() -> None:
    """Test entry_message resolves UUID to name when user_dir is provided."""
    uuid_hex = "a" * 32
    mock_entry = MagicMock(spec=LogEntry)
    mock_entry.event_code = 8
    mock_entry.user_info = uuid_hex
    mock_entry.extra_description = ""

    user_dir = {uuid_hex: "Alice"}
    msg = entry_message(mock_entry, user_dir)
    assert msg == "Opened by Alice"


def test_entry_message_without_actor() -> None:
    """Test entry_message returns just the event name when no actor."""
    mock_entry = MagicMock(spec=LogEntry)
    mock_entry.event_code = 9
    mock_entry.user_info = ""
    mock_entry.extra_description = ""

    msg = entry_message(mock_entry)
    assert msg == "Passage mode on"
