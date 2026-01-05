"""Test the Husqvarna Automower Bluetooth setup."""

from datetime import timedelta
from unittest.mock import Mock

from automower_ble.protocol import MowerActivity, MowerState
from bleak import BleakError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.lawn_mower import LawnMowerActivity
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed

pytestmark = pytest.mark.usefixtures("mock_automower_client")


@pytest.mark.parametrize(
    (
        "is_connected_side_effect",
        "is_connected_return_value",
        "connect_side_effect",
        "connect_return_value",
    ),
    [
        (None, False, None, False),
        (None, False, BleakError, False),
        (None, False, None, True),
        (BleakError, False, None, True),
    ],
)
async def test_setup_disconnect(
    hass: HomeAssistant,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    is_connected_side_effect: Exception,
    is_connected_return_value: bool,
    connect_side_effect: Exception,
    connect_return_value: bool,
) -> None:
    """Test disconnected device."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert hass.states.get("lawn_mower.husqvarna_automower").state != STATE_UNAVAILABLE

    mock_automower_client.is_connected.side_effect = is_connected_side_effect
    mock_automower_client.is_connected.return_value = is_connected_return_value
    mock_automower_client.connect.side_effect = connect_side_effect
    mock_automower_client.connect.return_value = connect_return_value

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("lawn_mower.husqvarna_automower").state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("attribute"),
    [
        "mower_activity",
        "mower_state",
        "battery_level",
    ],
)
async def test_invalid_data_received(
    hass: HomeAssistant,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    attribute: str,
) -> None:
    """Test invalid data received."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    getattr(mock_automower_client, attribute).return_value = None

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("lawn_mower.husqvarna_automower").state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("attribute"),
    [
        "mower_activity",
        "mower_state",
        "battery_level",
    ],
)
async def test_bleak_error_data_update(
    hass: HomeAssistant,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    attribute: str,
) -> None:
    """Test BleakError during data update."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    getattr(mock_automower_client, attribute).side_effect = BleakError

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("lawn_mower.husqvarna_automower").state == STATE_UNAVAILABLE


OPERATIONAL_STATES = [
    MowerState.IN_OPERATION,
    MowerState.PENDING_START,
    MowerState.RESTRICTED,
]


@pytest.mark.parametrize(
    ("mower_states", "mower_activities", "expected_state"),
    [
        # MowerState ERROR, FATAL_ERROR, OFF, STOPPED, WAIT_FOR_SAFETYPIN -> Mapped to
        # LawnMowerActivity.ERROR
        (
            [
                MowerState.ERROR,
                MowerState.FATAL_ERROR,
                MowerState.OFF,
                MowerState.STOPPED,
                MowerState.WAIT_FOR_SAFETYPIN,
            ],
            list(MowerActivity),
            LawnMowerActivity.ERROR,
        ),
        # MowerState PAUSED -> Mapped to LawnMowerActivity.PAUSED
        ([MowerState.PAUSED], list(MowerActivity), LawnMowerActivity.PAUSED),
        # Operational states are mapped according to the activity
        (
            OPERATIONAL_STATES,
            [MowerActivity.CHARGING, MowerActivity.PARKED],
            LawnMowerActivity.DOCKED,
        ),
        (
            OPERATIONAL_STATES,
            [MowerActivity.GOING_OUT, MowerActivity.MOWING],
            LawnMowerActivity.MOWING,
        ),
        (
            OPERATIONAL_STATES,
            [MowerActivity.GOING_HOME],
            LawnMowerActivity.RETURNING,
        ),
        (
            OPERATIONAL_STATES,
            [MowerActivity.STOPPED_IN_GARDEN],
            LawnMowerActivity.ERROR,
        ),
        # Special case for MowerActivity.NONE
        (
            [MowerState.IN_OPERATION, MowerState.RESTRICTED],
            [MowerActivity.NONE],
            LawnMowerActivity.DOCKED,
        ),
        (
            [MowerState.PENDING_START],
            [MowerActivity.NONE],
            LawnMowerActivity.ERROR,
        ),
    ],
)
async def test_mower_activity_mapping(
    hass: HomeAssistant,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mower_states: list[MowerState],
    mower_activities: list[MowerActivity],
    expected_state: str,
) -> None:
    """Test mower state and activity mapping to LawnMowerActivity states."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    for mower_state in mower_states:
        for mower_activity in mower_activities:
            mock_automower_client.mower_state.return_value = mower_state
            mock_automower_client.mower_activity.return_value = mower_activity

            freezer.tick(timedelta(seconds=60))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()

            assert (
                hass.states.get("lawn_mower.husqvarna_automower").state
                == expected_state
            )
