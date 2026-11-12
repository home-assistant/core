"""Test the Husqvarna Automower Bluetooth setup."""

from contextlib import AbstractContextManager
from datetime import timedelta
from unittest.mock import Mock, PropertyMock, patch

from automower_ble.protocol import MowerActivity, MowerState, ResponseResult
from bleak import BleakError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.husqvarna_automower_ble.lawn_mower import (
    AutomowerLawnMower,
)
from homeassistant.components.lawn_mower import (
    DOMAIN as LAWN_MOWER_DOMAIN,
    SERVICE_DOCK,
    SERVICE_PAUSE,
    SERVICE_START_MOWING,
    LawnMowerActivity,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

pytestmark = pytest.mark.usefixtures("mock_automower_client")

ENTITY_ID = "lawn_mower.garden_husqvarna_automower"


def _available_despite_dropped_connection() -> AbstractContextManager[PropertyMock]:
    """Keep the entity available so service calls reach it.

    Unavailable entities are skipped by service calls, so this simulates the
    connection dropping after the availability check.
    """
    return patch.object(
        AutomowerLawnMower, "available", new_callable=PropertyMock, return_value=True
    )


SERVICES = [
    pytest.param(SERVICE_START_MOWING, "mower_resume", id="start_mowing"),
    pytest.param(SERVICE_DOCK, "mower_park", id="dock"),
    pytest.param(SERVICE_PAUSE, "mower_pause", id="pause"),
]


@pytest.mark.parametrize(("service", "mower_method"), SERVICES)
async def test_service_reconnects(
    hass: HomeAssistant,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
    service: str,
    mower_method: str,
) -> None:
    """Test a service reconnects to a disconnected mower and sends the command."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_automower_client.is_connected.return_value = False
    mock_automower_client.connect.reset_mock()

    async def _connect(device: Mock) -> ResponseResult:
        mock_automower_client.is_connected.return_value = True
        return ResponseResult.OK

    mock_automower_client.connect.side_effect = _connect

    with (
        _available_despite_dropped_connection(),
        patch(
            "homeassistant.components.husqvarna_automower_ble.lawn_mower.bluetooth."
            "async_ble_device_from_address",
            return_value=Mock(),
        ),
    ):
        await hass.services.async_call(
            LAWN_MOWER_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )

    mock_automower_client.connect.assert_awaited_once()
    getattr(mock_automower_client, mower_method).assert_awaited_once()


@pytest.mark.parametrize(("service", "mower_method"), SERVICES)
@pytest.mark.parametrize(
    ("device", "connect_side_effect", "connect_return_value", "cause"),
    [
        pytest.param(None, None, ResponseResult.OK, type(None), id="device_not_found"),
        pytest.param(Mock(), BleakError, ResponseResult.OK, BleakError, id="bleak"),
        pytest.param(
            Mock(), TimeoutError, ResponseResult.OK, TimeoutError, id="timeout"
        ),
        pytest.param(
            Mock(), None, ResponseResult.UNKNOWN_ERROR, type(None), id="not_ok"
        ),
    ],
)
async def test_service_reconnect_failed(
    hass: HomeAssistant,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
    service: str,
    mower_method: str,
    device: Mock | None,
    connect_side_effect: type[Exception] | None,
    connect_return_value: ResponseResult,
    cause: type[BaseException | None],
) -> None:
    """Test a failed reconnect raises an error instead of reporting success."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_automower_client.is_connected.return_value = False
    mock_automower_client.connect.side_effect = connect_side_effect
    mock_automower_client.connect.return_value = connect_return_value

    with (
        _available_despite_dropped_connection(),
        patch(
            "homeassistant.components.husqvarna_automower_ble.lawn_mower.bluetooth."
            "async_ble_device_from_address",
            return_value=device,
        ),
        pytest.raises(
            HomeAssistantError,
            match=f"Unable to reconnect to device {mock_config_entry.data['address']}",
        ) as exc_info,
    ):
        await hass.services.async_call(
            LAWN_MOWER_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )

    assert type(exc_info.value.__cause__) is cause
    getattr(mock_automower_client, mower_method).assert_not_awaited()


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

    assert (
        hass.states.get("lawn_mower.garden_husqvarna_automower").state
        != STATE_UNAVAILABLE
    )

    mock_automower_client.is_connected.side_effect = is_connected_side_effect
    mock_automower_client.is_connected.return_value = is_connected_return_value
    mock_automower_client.connect.side_effect = connect_side_effect
    mock_automower_client.connect.return_value = connect_return_value

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("lawn_mower.garden_husqvarna_automower").state
        == STATE_UNAVAILABLE
    )


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

    assert (
        hass.states.get("lawn_mower.garden_husqvarna_automower").state
        == STATE_UNAVAILABLE
    )


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

    assert (
        hass.states.get("lawn_mower.garden_husqvarna_automower").state
        == STATE_UNAVAILABLE
    )


OPERATIONAL_STATES = [
    MowerState.IN_OPERATION,
    MowerState.PENDING_START,
    MowerState.RESTRICTED,
]


@pytest.mark.parametrize(
    ("mower_states", "mower_activities", "expected_state"),
    [
        # MowerState ERROR, FATAL_ERROR -> Mapped to LawnMowerActivity.ERROR
        (
            [
                MowerState.ERROR,
                MowerState.FATAL_ERROR,
            ],
            list(MowerActivity),
            LawnMowerActivity.ERROR,
        ),
        # MowerState OFF, STOPPED, WAIT_FOR_SAFETYPIN -> Mapped to
        # LawnMowerActivity.IDLE
        (
            [
                MowerState.OFF,
                MowerState.STOPPED,
                MowerState.WAIT_FOR_SAFETYPIN,
            ],
            list(MowerActivity),
            LawnMowerActivity.IDLE,
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
                hass.states.get("lawn_mower.garden_husqvarna_automower").state
                == expected_state
            )
