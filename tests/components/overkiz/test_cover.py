"""Tests for the Overkiz cover platform."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, Mock, call

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState, UIClass
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import CoverDeviceClass, CoverEntityFeature
from homeassistant.components.overkiz.cover import (
    async_setup_entry as async_setup_cover_entry,
)
from homeassistant.components.overkiz.cover.awning import Awning
from homeassistant.components.overkiz.cover.vertical_cover import (
    LowSpeedCover,
    VerticalCover,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import clone_device, create_coordinator, get_fixture_device, set_runtime_data

from tests.common import MockConfigEntry, snapshot_platform

FIXTURE_DEVICE = get_fixture_device(ui_class=UIClass.ROLLER_SHUTTER)


async def test_cover_entities_snapshot(
    hass: HomeAssistant,
    setup_overkiz_integration,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the cover entities via a snapshot smoke test."""
    config_entry = await setup_overkiz_integration(platforms=[Platform.COVER])

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_cls", "expected_count"),
    [(Awning, 1), (VerticalCover, 2), (LowSpeedCover, 1)],
)
async def test_async_setup_entry_creates_expected_cover_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_cls: type[Awning | VerticalCover | LowSpeedCover],
    expected_count: int,
) -> None:
    """Test the cover platform creates the expected entity classes."""
    awning = clone_device(
        FIXTURE_DEVICE,
        device_url="io://gateway-id/awning",
        ui_class=UIClass.AWNING,
        commands=[OverkizCommand.DEPLOY, OverkizCommand.UNDEPLOY],
    )
    shutter = clone_device(
        FIXTURE_DEVICE,
        device_url="io://gateway-id/shutter",
        ui_class=UIClass.ROLLER_SHUTTER,
        commands=[OverkizCommand.OPEN, OverkizCommand.CLOSE, OverkizCommand.STOP],
    )
    low_speed = clone_device(
        FIXTURE_DEVICE,
        device_url="io://gateway-id/low-speed",
        ui_class=UIClass.GATE,
        commands=[OverkizCommand.SET_CLOSURE_AND_LINEAR_SPEED],
    )
    entry = set_runtime_data(
        mock_config_entry,
        create_coordinator(hass, mock_config_entry, awning, shutter, low_speed),
        platforms={Platform.COVER: [awning, shutter, low_speed]},
    )
    async_add_entities = Mock()

    await async_setup_cover_entry(hass, entry, async_add_entities)

    entities = async_add_entities.call_args.args[0]
    assert sum(type(entity) is entity_cls for entity in entities) == expected_count


async def test_vertical_cover_commands_and_position_mapping(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test vertical cover commands and inverted position mapping."""
    device = clone_device(
        FIXTURE_DEVICE,
        device_url="io://gateway-id/vertical",
        ui_class=UIClass.ROLLER_SHUTTER,
        commands=[
            OverkizCommand.UP,
            OverkizCommand.DOWN,
            OverkizCommand.MY,
            OverkizCommand.SET_CLOSURE,
        ],
        states={OverkizState.CORE_CLOSURE: 40},
    )
    cover = VerticalCover(
        device.device_url, create_coordinator(hass, mock_config_entry, device)
    )
    cover.executor.async_execute_command = AsyncMock()

    assert cover.current_cover_position == 60

    await cover.async_open_cover()
    await cover.async_close_cover()
    await cover.async_stop_cover()
    await cover.async_set_cover_position(position=25)

    assert cover.executor.async_execute_command.await_args_list == [
        call(OverkizCommand.UP),
        call(OverkizCommand.DOWN),
        call(OverkizCommand.MY),
        call(OverkizCommand.SET_CLOSURE, 75),
    ]


async def test_vertical_cover_tilt_commands_and_supported_features(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test tilt commands, tilt position mapping, and supported features."""
    device = clone_device(
        FIXTURE_DEVICE,
        device_url="io://gateway-id/vertical",
        ui_class=UIClass.ROLLER_SHUTTER,
        commands=[
            OverkizCommand.OPEN_SLATS,
            OverkizCommand.CLOSE_SLATS,
            OverkizCommand.MY,
            OverkizCommand.SET_ORIENTATION,
        ],
        states={OverkizState.CORE_SLATS_ORIENTATION: 30},
    )
    cover = VerticalCover(
        device.device_url, create_coordinator(hass, mock_config_entry, device)
    )
    cover.executor.async_execute_command = AsyncMock()

    assert cover.current_cover_tilt_position == 70
    assert cover.supported_features & CoverEntityFeature.OPEN_TILT
    assert cover.supported_features & CoverEntityFeature.CLOSE_TILT
    assert cover.supported_features & CoverEntityFeature.STOP_TILT
    assert cover.supported_features & CoverEntityFeature.SET_TILT_POSITION

    await cover.async_open_cover_tilt()
    await cover.async_close_cover_tilt()
    await cover.async_stop_cover_tilt()
    await cover.async_set_cover_tilt_position(tilt_position=40)

    assert cover.executor.async_execute_command.await_args_list == [
        call(OverkizCommand.OPEN_SLATS),
        call(OverkizCommand.CLOSE_SLATS),
        call(OverkizCommand.MY),
        call(OverkizCommand.SET_ORIENTATION, 60),
    ]


@pytest.mark.parametrize(
    ("states", "expected"),
    [
        (
            {
                OverkizState.CORE_OPEN_CLOSED: OverkizCommandParam.CLOSED,
                OverkizState.CORE_PEDESTRIAN_POSITION: 50,
            },
            True,
        ),
        ({OverkizState.CORE_CLOSURE: 100}, True),
        ({OverkizState.CORE_SLATS_ORIENTATION: 100}, True),
        ({}, None),
    ],
)
def test_is_closed_uses_state_position_and_tilt_fallbacks(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    states: dict[str, Any],
    expected: bool | None,
) -> None:
    """Test closed-state precedence and fallbacks."""
    device = clone_device(
        FIXTURE_DEVICE,
        device_url="io://gateway-id/vertical",
        ui_class=UIClass.ROLLER_SHUTTER,
        commands=[],
        states=states,
    )
    cover = VerticalCover(
        device.device_url, create_coordinator(hass, mock_config_entry, device)
    )

    assert cover.is_closed is expected


@pytest.mark.parametrize(
    ("states", "expected_opening", "expected_closing"),
    [
        (
            {
                OverkizState.CORE_MOVING: True,
                OverkizState.CORE_CLOSURE: 75,
                OverkizState.CORE_TARGET_CLOSURE: 20,
            },
            True,
            False,
        ),
        (
            {
                OverkizState.CORE_MOVING: True,
                OverkizState.CORE_CLOSURE: 20,
                OverkizState.CORE_TARGET_CLOSURE: 75,
            },
            False,
            True,
        ),
    ],
)
def test_vertical_cover_movement_state_fallback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    states: dict[str, Any],
    expected_opening: bool,
    expected_closing: bool,
) -> None:
    """Test vertical cover movement fallback based on target closure."""
    device = clone_device(
        FIXTURE_DEVICE,
        device_url="io://gateway-id/vertical",
        ui_class=UIClass.ROLLER_SHUTTER,
        commands=[],
        states=states,
    )
    cover = VerticalCover(
        device.device_url, create_coordinator(hass, mock_config_entry, device)
    )

    assert cover.is_opening is expected_opening
    assert cover.is_closing is expected_closing


def test_vertical_cover_reports_running_execution(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test running executions take precedence for opening state."""
    device = clone_device(
        FIXTURE_DEVICE,
        device_url="io://gateway-id/vertical",
        ui_class=UIClass.ROLLER_SHUTTER,
        commands=[],
    )
    coordinator = create_coordinator(hass, mock_config_entry, device)
    cover = VerticalCover(device.device_url, coordinator)
    coordinator.executions = {
        "exec-id": {
            "command_name": OverkizCommand.OPEN,
            "device_url": cover.device.device_url,
        }
    }

    assert cover.is_opening is True
    assert cover.is_closing is None


async def test_awning_commands_state_mapping_and_features(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test awning command handling and direct deployment mapping."""
    device = clone_device(
        FIXTURE_DEVICE,
        device_url="io://gateway-id/awning",
        ui_class=UIClass.AWNING,
        commands=[
            OverkizCommand.DEPLOY,
            OverkizCommand.UNDEPLOY,
            OverkizCommand.MY,
            OverkizCommand.SET_DEPLOYMENT,
        ],
        states={OverkizState.CORE_DEPLOYMENT: 35},
    )
    awning = Awning(
        device.device_url, create_coordinator(hass, mock_config_entry, device)
    )
    awning.executor.async_execute_command = AsyncMock()

    assert awning.current_cover_position == 35
    assert awning.supported_features & CoverEntityFeature.OPEN
    assert awning.supported_features & CoverEntityFeature.CLOSE
    assert awning.supported_features & CoverEntityFeature.STOP
    assert awning.supported_features & CoverEntityFeature.SET_POSITION
    assert awning.device_class is CoverDeviceClass.AWNING

    await awning.async_open_cover()
    await awning.async_close_cover()
    await awning.async_stop_cover()
    await awning.async_set_cover_position(position=80)

    assert awning.executor.async_execute_command.await_args_list == [
        call(OverkizCommand.DEPLOY),
        call(OverkizCommand.UNDEPLOY),
        call(OverkizCommand.MY),
        call(OverkizCommand.SET_DEPLOYMENT, 80),
    ]


@pytest.mark.parametrize(
    ("states", "expected_opening", "expected_closing"),
    [
        (
            {
                OverkizState.CORE_MOVING: True,
                OverkizState.CORE_DEPLOYMENT: 20,
                OverkizState.CORE_TARGET_CLOSURE: 80,
            },
            True,
            False,
        ),
        (
            {
                OverkizState.CORE_MOVING: True,
                OverkizState.CORE_DEPLOYMENT: 80,
                OverkizState.CORE_TARGET_CLOSURE: 20,
            },
            False,
            True,
        ),
    ],
)
def test_awning_movement_state_fallback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    states: dict[str, Any],
    expected_opening: bool,
    expected_closing: bool,
) -> None:
    """Test awning movement fallback based on deployment position."""
    device = clone_device(
        FIXTURE_DEVICE,
        device_url="io://gateway-id/awning",
        ui_class=UIClass.AWNING,
        commands=[],
        states=states,
    )
    awning = Awning(
        device.device_url, create_coordinator(hass, mock_config_entry, device)
    )

    assert awning.is_opening is expected_opening
    assert awning.is_closing is expected_closing


async def test_low_speed_cover_uses_low_speed_parameter_and_unique_id_suffix(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the low-speed cover command payload and unique id."""
    device = clone_device(
        FIXTURE_DEVICE,
        device_url="io://gateway-id/low-speed",
        ui_class=UIClass.GATE,
        commands=[OverkizCommand.SET_CLOSURE_AND_LINEAR_SPEED],
    )
    cover = LowSpeedCover(
        device.device_url, create_coordinator(hass, mock_config_entry, device)
    )
    cover.executor.async_execute_command = AsyncMock()

    assert cover.unique_id.endswith("_low_speed")

    await cover.async_open_cover()
    await cover.async_close_cover()
    await cover.async_set_cover_position(position=35)

    assert cover.executor.async_execute_command.await_args_list == [
        call(
            OverkizCommand.SET_CLOSURE_AND_LINEAR_SPEED, 0, OverkizCommandParam.LOWSPEED
        ),
        call(
            OverkizCommand.SET_CLOSURE_AND_LINEAR_SPEED,
            100,
            OverkizCommandParam.LOWSPEED,
        ),
        call(
            OverkizCommand.SET_CLOSURE_AND_LINEAR_SPEED,
            65,
            OverkizCommandParam.LOWSPEED,
        ),
    ]


def test_vertical_cover_device_class_and_supported_features(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test vertical cover device class mapping and supported features."""
    device = clone_device(
        FIXTURE_DEVICE,
        device_url="io://gateway-id/vertical",
        ui_class=UIClass.GARAGE_DOOR,
        commands=[
            OverkizCommand.OPEN,
            OverkizCommand.CLOSE,
            OverkizCommand.STOP,
            OverkizCommand.SET_CLOSURE,
            OverkizCommand.OPEN_SLATS,
            OverkizCommand.CLOSE_SLATS,
            OverkizCommand.SET_ORIENTATION,
        ],
    )
    cover = VerticalCover(
        device.device_url, create_coordinator(hass, mock_config_entry, device)
    )

    assert cover.device_class is CoverDeviceClass.GARAGE
    assert cover.supported_features & CoverEntityFeature.OPEN
    assert cover.supported_features & CoverEntityFeature.CLOSE
    assert cover.supported_features & CoverEntityFeature.STOP
    assert cover.supported_features & CoverEntityFeature.SET_POSITION
    assert cover.supported_features & CoverEntityFeature.OPEN_TILT
    assert cover.supported_features & CoverEntityFeature.CLOSE_TILT
    assert cover.supported_features & CoverEntityFeature.SET_TILT_POSITION
