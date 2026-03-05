"""Tests for ZoneMinder camera entities."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, PropertyMock, patch

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.camera import CameraState
from homeassistant.components.zoneminder.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import create_mock_monitor, create_mock_zm_client

from tests.common import async_fire_time_changed


async def _setup_zm_with_cameras(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    config: dict,
    monitors: list,
    freezer: FrozenDateTimeFactory,
    verify_ssl: bool = True,
) -> None:
    """Set up ZM component with camera platform and given monitors."""
    mock_zoneminder_client.get_monitors.return_value = monitors
    type(mock_zoneminder_client).verify_ssl = PropertyMock(return_value=verify_ssl)

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done(wait_background_tasks=True)
    # Camera uses setup_platform (sync), add camera platform explicitly
    assert await async_setup_component(
        hass,
        "camera",
        {"camera": [{"platform": DOMAIN}]},
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    # Trigger first poll to update entity state
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_one_camera_per_monitor(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    two_monitors: list,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test one camera entity is created per monitor."""
    await _setup_zm_with_cameras(
        hass, mock_zoneminder_client, single_server_config, two_monitors, freezer
    )

    states = hass.states.async_all("camera")
    assert len(states) == 2


async def test_camera_entity_name(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test camera entity name matches monitor name."""
    monitors = [create_mock_monitor(name="Front Door")]
    await _setup_zm_with_cameras(
        hass, mock_zoneminder_client, single_server_config, monitors, freezer
    )

    state = hass.states.get("camera.front_door")
    assert state is not None
    assert state.name == "Front Door"


async def test_camera_recording_state(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test camera recording state reflects monitor is_recording."""
    monitors = [
        create_mock_monitor(name="Recording Cam", is_recording=True, is_available=True)
    ]
    await _setup_zm_with_cameras(
        hass, mock_zoneminder_client, single_server_config, monitors, freezer
    )

    state = hass.states.get("camera.recording_cam")
    assert state is not None
    assert state.state == CameraState.RECORDING


async def test_camera_idle_state(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test camera idle state when not recording."""
    monitors = [
        create_mock_monitor(name="Idle Cam", is_recording=False, is_available=True)
    ]
    await _setup_zm_with_cameras(
        hass, mock_zoneminder_client, single_server_config, monitors, freezer
    )

    state = hass.states.get("camera.idle_cam")
    assert state is not None
    assert state.state == CameraState.IDLE


async def test_camera_unavailable_state(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test camera unavailable state tracking."""
    monitors = [create_mock_monitor(name="Offline Cam", is_available=False)]
    await _setup_zm_with_cameras(
        hass, mock_zoneminder_client, single_server_config, monitors, freezer
    )

    state = hass.states.get("camera.offline_cam")
    assert state is not None
    assert state.state == "unavailable"


async def test_no_monitors_raises_platform_not_ready(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
) -> None:
    """Test PlatformNotReady raised when no monitors returned."""
    mock_zoneminder_client.get_monitors.return_value = []

    assert await async_setup_component(hass, DOMAIN, single_server_config)
    await hass.async_block_till_done()
    await async_setup_component(
        hass,
        "camera",
        {"camera": [{"platform": DOMAIN}]},
    )
    await hass.async_block_till_done()

    # No camera entities should exist
    states = hass.states.async_all("camera")
    assert len(states) == 0


async def test_multi_server_camera_creation(
    hass: HomeAssistant,
    multi_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test cameras created from multiple ZM servers."""
    monitors1 = [create_mock_monitor(monitor_id=1, name="Front Door")]
    monitors2 = [create_mock_monitor(monitor_id=2, name="Back Yard")]

    clients = iter(
        [
            create_mock_zm_client(monitors=monitors1),
            create_mock_zm_client(monitors=monitors2),
        ]
    )

    with patch(
        "homeassistant.components.zoneminder.ZoneMinder",
        side_effect=lambda *args, **kwargs: next(clients),
    ):
        assert await async_setup_component(hass, DOMAIN, multi_server_config)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert await async_setup_component(
            hass,
            "camera",
            {"camera": [{"platform": DOMAIN}]},
        )
        await hass.async_block_till_done(wait_background_tasks=True)
        freezer.tick(timedelta(seconds=60))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    states = hass.states.async_all("camera")
    assert len(states) == 2


async def test_filter_urllib3_logging_called(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test filter_urllib3_logging() is called in setup_platform."""
    monitors = [create_mock_monitor(name="Front Door")]

    with patch(
        "homeassistant.components.zoneminder.camera.filter_urllib3_logging"
    ) as mock_filter:
        await _setup_zm_with_cameras(
            hass, mock_zoneminder_client, single_server_config, monitors, freezer
        )

    mock_filter.assert_called_once()
