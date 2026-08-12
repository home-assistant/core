"""Test the liebherr integration init."""

import copy
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyliebherrhomeapi import (
    AutoDoorControl,
    Device,
    DeviceState,
    DeviceType,
    DoorState,
    IceMakerControl,
    IceMakerMode,
    TemperatureControl,
    TemperatureUnit,
    ToggleControl,
    ZonePosition,
)
from pyliebherrhomeapi.exceptions import (
    LiebherrAuthenticationError,
    LiebherrConnectionError,
    LiebherrNotFoundError,
    LiebherrPreconditionFailedError,
    LiebherrTimeoutError,
)
import pytest

from homeassistant.components.liebherr.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import MOCK_DEVICE, MOCK_DEVICE_STATE, SSEStreamHelper

from tests.common import MockConfigEntry, async_fire_time_changed


# Test errors during initial get_devices() call in async_setup_entry
@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (LiebherrAuthenticationError("Invalid API key"), ConfigEntryState.SETUP_ERROR),
        (LiebherrConnectionError("Connection failed"), ConfigEntryState.SETUP_RETRY),
    ],
    ids=["auth_failed", "connection_error"],
)
async def test_setup_entry_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_liebherr_client: MagicMock,
    side_effect: Any,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup handles various error conditions."""
    mock_config_entry.add_to_hass(hass)
    mock_liebherr_client.get_devices.side_effect = side_effect

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


# Test errors during get_device() call in coordinator setup
# (after successful get_devices)
@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (LiebherrAuthenticationError("Invalid API key"), ConfigEntryState.SETUP_ERROR),
        (LiebherrConnectionError("Connection failed"), ConfigEntryState.SETUP_RETRY),
    ],
    ids=["auth_failed", "connection_error"],
)
async def test_coordinator_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_liebherr_client: MagicMock,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test coordinator setup handles device access errors."""
    mock_config_entry.add_to_hass(hass)
    mock_liebherr_client.get_devices.return_value = [MOCK_DEVICE]
    mock_liebherr_client.get_device.side_effect = side_effect

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (LiebherrAuthenticationError("Invalid API key"), ConfigEntryState.SETUP_ERROR),
        (LiebherrTimeoutError("Request timed out"), ConfigEntryState.SETUP_RETRY),
    ],
    ids=["auth_failed", "timeout"],
)
async def test_coordinator_initial_refresh_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_liebherr_client: MagicMock,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test coordinator initial refresh errors."""
    mock_config_entry.add_to_hass(hass)
    mock_liebherr_client.get_device_state.side_effect = side_effect

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


@pytest.mark.usefixtures("init_integration")
async def test_start_stream_is_idempotent(
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test starting an active stream does not create another task."""
    coordinator = mock_config_entry.runtime_data.coordinators[MOCK_DEVICE.device_id]
    stream_task = coordinator._stream_task

    coordinator.async_start_stream()

    assert coordinator._stream_task is stream_task


@pytest.mark.usefixtures("init_integration")
async def test_stream_delta_preserves_same_control_in_other_zone(
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    sse_helper: SSEStreamHelper,
) -> None:
    """Test a zoned control delta preserves same-name controls in other zones."""
    coordinator = mock_config_entry.runtime_data.coordinators[MOCK_DEVICE.device_id]
    zone_1 = AutoDoorControl(
        name="autodoor",
        type="AutoDoorControl",
        zone_id=1,
        zone_position=ZonePosition.TOP,
        value=DoorState.CLOSED,
    )
    zone_2 = AutoDoorControl(
        name="autodoor",
        type="AutoDoorControl",
        zone_id=2,
        zone_position=ZonePosition.BOTTOM,
        value=DoorState.CLOSED,
    )
    coordinator.async_set_updated_data(
        DeviceState(device=MOCK_DEVICE, controls=[zone_1, zone_2])
    )
    updated_zone_1 = AutoDoorControl(
        name="autodoor",
        type="AutoDoorControl",
        zone_id=1,
        zone_position=ZonePosition.TOP,
        value=DoorState.OPEN,
    )
    mock_liebherr_client.get_device_state.side_effect = lambda *args, **kwargs: (
        DeviceState(device=MOCK_DEVICE, controls=[updated_zone_1])
    )

    await sse_helper.async_push()

    assert coordinator.data is not None
    assert [
        control
        for control in coordinator.data.controls
        if isinstance(control, AutoDoorControl)
    ] == [updated_zone_1, zone_2]


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "exception",
    [
        LiebherrNotFoundError("Device not found"),
        LiebherrPreconditionFailedError("Device not onboarded"),
    ],
    ids=["not_found", "precondition_failed"],
)
async def test_terminal_stream_error_marks_entities_unavailable(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    sse_helper: SSEStreamHelper,
    exception: Exception,
) -> None:
    """Test terminal stream errors mark entities unavailable."""
    mock_liebherr_client.get_device_state.side_effect = exception

    await sse_helper.async_push()

    state = hass.states.get("sensor.test_fridge_top_zone")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_repeated_stream_disconnect(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    sse_helper: SSEStreamHelper,
) -> None:
    """Test repeated stream disconnects leave entities unavailable."""
    mock_liebherr_client.get_device_state.side_effect = LiebherrConnectionError(
        "Connection failed"
    )

    await sse_helper.async_push()
    await sse_helper.async_push()

    state = hass.states.get("sensor.test_fridge_top_zone")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_liebherr_client: MagicMock,
) -> None:
    """Test successful unload of entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


NEW_DEVICE = Device(
    device_id="new_device_id",
    nickname="New Fridge",
    device_type=DeviceType.FRIDGE,
    device_name="K2601",
)

NEW_DEVICE_STATE = DeviceState(
    device=NEW_DEVICE,
    controls=[
        TemperatureControl(
            zone_id=1,
            zone_position=ZonePosition.TOP,
            name="Fridge",
            type="fridge",
            value=4,
            target=5,
            min=2,
            max=8,
            unit=TemperatureUnit.CELSIUS,
        ),
        ToggleControl(
            name="supercool",
            type="ToggleControl",
            zone_id=1,
            zone_position=ZonePosition.TOP,
            value=False,
        ),
        IceMakerControl(
            name="icemaker",
            type="IceMakerControl",
            zone_id=1,
            zone_position=ZonePosition.TOP,
            ice_maker_mode=IceMakerMode.OFF,
            has_max_ice=False,
        ),
    ],
)


@pytest.mark.usefixtures("init_integration")
async def test_dynamic_device_discovery_no_new_devices(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device scan with no new devices does not create entities."""
    # Same devices returned
    mock_liebherr_client.get_devices.return_value = [MOCK_DEVICE]

    initial_states = len(hass.states.async_all())

    freezer.tick(timedelta(minutes=5, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # No new entities should be created
    assert len(hass.states.async_all()) == initial_states


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "exception",
    [
        LiebherrConnectionError("Connection failed"),
        LiebherrAuthenticationError("Auth failed"),
    ],
    ids=["connection_error", "auth_error"],
)
async def test_dynamic_device_discovery_api_error(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test device scan gracefully handles API errors."""
    mock_liebherr_client.get_devices.side_effect = exception

    initial_states = len(hass.states.async_all())

    freezer.tick(timedelta(minutes=5, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # No crash, no new entities
    assert len(hass.states.async_all()) == initial_states
    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("init_integration")
async def test_dynamic_device_discovery_unexpected_error(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device scan gracefully handles unexpected errors."""
    mock_liebherr_client.get_devices.side_effect = RuntimeError("Unexpected")

    initial_states = len(hass.states.async_all())

    freezer.tick(timedelta(minutes=5, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # No crash, no new entities
    assert len(hass.states.async_all()) == initial_states
    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("init_integration")
async def test_dynamic_device_discovery_coordinator_setup_failure(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device scan skips devices that fail coordinator setup."""
    # New device appears but its state fetch fails
    mock_liebherr_client.get_devices.return_value = [MOCK_DEVICE, NEW_DEVICE]

    original_state = copy.deepcopy(MOCK_DEVICE_STATE)
    mock_liebherr_client.get_device_state.side_effect = lambda device_id, **kw: (
        copy.deepcopy(original_state)
        if device_id == "test_device_id"
        else (_ for _ in ()).throw(LiebherrConnectionError("Device offline"))
    )

    freezer.tick(timedelta(minutes=5, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # New device should NOT be added
    assert not device_registry.async_get_device_by_identifier(
        (DOMAIN, "new_device_id"), mock_config_entry.entry_id
    )
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_dynamic_device_discovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_liebherr_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test new devices are automatically discovered on all platforms."""
    mock_config_entry.add_to_hass(hass)

    all_platforms = [
        Platform.SENSOR,
        Platform.NUMBER,
        Platform.SWITCH,
        Platform.SELECT,
    ]
    with patch(f"homeassistant.components.{DOMAIN}.PLATFORMS", all_platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Initially only the original device exists
    assert hass.states.get("sensor.test_fridge_top_zone") is not None
    assert hass.states.get("sensor.new_fridge") is None

    # Simulate a new device appearing on the account
    mock_liebherr_client.get_devices.return_value = [MOCK_DEVICE, NEW_DEVICE]
    mock_liebherr_client.get_device_state.side_effect = lambda device_id, **kw: (
        copy.deepcopy(
            NEW_DEVICE_STATE if device_id == "new_device_id" else MOCK_DEVICE_STATE
        )
    )

    # Advance time to trigger device scan (5 minute interval)
    freezer.tick(timedelta(minutes=5, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # New device should have entities on all platforms
    state = hass.states.get("sensor.new_fridge")
    assert state is not None
    assert state.state == "4"
    assert hass.states.get("number.new_fridge_setpoint") is not None
    assert hass.states.get("switch.new_fridge_supercool") is not None
    assert hass.states.get("select.new_fridge_icemaker") is not None

    # Original device should still exist
    assert hass.states.get("sensor.test_fridge_top_zone") is not None

    # Both devices should be in the device registry
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "new_device_id"), mock_config_entry.entry_id
    )
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "test_device_id"), mock_config_entry.entry_id
    )


async def test_stale_device_removal(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_liebherr_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test stale devices are removed when no longer returned by the API."""
    mock_config_entry.add_to_hass(hass)

    all_platforms = [
        Platform.SENSOR,
        Platform.NUMBER,
        Platform.SWITCH,
        Platform.SELECT,
    ]

    # Start with two devices
    mock_liebherr_client.get_devices.return_value = [MOCK_DEVICE, NEW_DEVICE]
    mock_liebherr_client.get_device_state.side_effect = lambda device_id, **kw: (
        copy.deepcopy(
            NEW_DEVICE_STATE if device_id == "new_device_id" else MOCK_DEVICE_STATE
        )
    )

    with patch(f"homeassistant.components.{DOMAIN}.PLATFORMS", all_platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Both devices should exist
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "test_device_id"), mock_config_entry.entry_id
    )
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "new_device_id"), mock_config_entry.entry_id
    )
    assert hass.states.get("sensor.test_fridge_top_zone") is not None
    assert hass.states.get("sensor.new_fridge") is not None

    # Verify both devices are in the device registry
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "test_device_id"), mock_config_entry.entry_id
    )
    new_device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "new_device_id"), mock_config_entry.entry_id
    )
    assert new_device_entry

    # Simulate the new device being removed from the account.
    # Make get_device_state raise for new_device_id so we can detect
    # if the stale coordinator is still consuming its stream after shutdown.
    mock_liebherr_client.get_devices.return_value = [MOCK_DEVICE]

    def _get_device_state_after_removal(device_id: str, **kw: Any) -> DeviceState:
        if device_id == "new_device_id":
            raise AssertionError(
                "get_device_state called for removed device new_device_id"
            )
        return copy.deepcopy(MOCK_DEVICE_STATE)

    mock_liebherr_client.get_device_state.side_effect = _get_device_state_after_removal

    freezer.tick(timedelta(minutes=5, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Stale device should be removed from device registry
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "test_device_id"), mock_config_entry.entry_id
    )
    assert not device_registry.async_get_device_by_identifier(
        (DOMAIN, "new_device_id"), mock_config_entry.entry_id
    )

    # Trigger a stream event for the removed device to confirm the stale
    # coordinator's stream task was cancelled (would raise AssertionError above)
    await mock_liebherr_client._sse_helper.async_push("new_device_id")

    # Original device should still work
    assert hass.states.get("sensor.test_fridge_top_zone") is not None
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_stale_device_removal_without_coordinator(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_liebherr_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test stale devices removed before startup are cleaned up on scan."""
    mock_config_entry.add_to_hass(hass)

    # Create a device registry entry for a device that was previously known
    # but is no longer returned by the API (removed while HA was offline).
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "old_device_id")},
        name="Old Appliance",
    )
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "old_device_id"), mock_config_entry.entry_id
    )

    # Start integration — only MOCK_DEVICE is returned, so no coordinator
    # is created for "old_device_id".
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # The orphaned device still exists in the registry after setup
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "old_device_id"), mock_config_entry.entry_id
    )
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "test_device_id"), mock_config_entry.entry_id
    )

    # Trigger the periodic device scan
    freezer.tick(timedelta(minutes=5, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # The orphaned device should now be removed from the registry
    assert not device_registry.async_get_device_by_identifier(
        (DOMAIN, "old_device_id"), mock_config_entry.entry_id
    )
    # The active device should still be present
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "test_device_id"), mock_config_entry.entry_id
    )
    assert mock_config_entry.state is ConfigEntryState.LOADED
