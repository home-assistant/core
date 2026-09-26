"""Tests for the Bosch SHC event platform."""

from unittest.mock import MagicMock

from boschshcpy import AlarmService
import pytest

from homeassistant.core import HomeAssistant

from .conftest import (
    motion_detector2_device,
    motion_detector_device,
    setup_integration,
    smoke_detector_device,
)

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "device_buckets",
    [{"motion_detectors": [motion_detector_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_motion_detector_no_motion_yet(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A Motion Detector's event entity exists but has no state before a motion event fires."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("event.motion_detector")
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.parametrize(
    "device_buckets",
    [{"motion_detectors": [motion_detector_device()]}],
    indirect=True,
)
async def test_motion_detector_fires_on_new_timestamp(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A LatestMotion push updates the event entity's state and attributes."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.motion_detectors[0]
    latest_motion_service = device.device_services[0]

    device.latestmotion = "2026-09-25T12:00:00.000Z"
    latest_motion_service._event_callbacks[device.id]()
    await hass.async_block_till_done()

    state = hass.states.get("event.motion_detector")
    assert state is not None
    assert state.state != "unknown"
    assert state.attributes["event_type"] == "motion"
    assert state.attributes["last_time_triggered"] == "2026-09-25T12:00:00.000Z"


@pytest.mark.parametrize(
    "device_buckets",
    [{"motion_detectors": [motion_detector_device()]}],
    indirect=True,
)
async def test_motion_detector_dedup_guard(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A phantom replay of the same latestmotion timestamp does not refire the event."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.motion_detectors[0]
    latest_motion_service = device.device_services[0]

    device.latestmotion = "2026-09-25T12:00:00.000Z"
    latest_motion_service._event_callbacks[device.id]()
    await hass.async_block_till_done()
    first_state = hass.states.get("event.motion_detector")
    assert first_state is not None

    latest_motion_service._event_callbacks[device.id]()
    await hass.async_block_till_done()
    second_state = hass.states.get("event.motion_detector")
    assert second_state is not None
    assert second_state.last_changed == first_state.last_changed


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "motion_detectors": [
                motion_detector_device(latestmotion="2026-09-25T09:00:00.000Z")
            ]
        }
    ],
    indirect=True,
)
async def test_motion_detector_no_replay_on_startup(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A pre-existing latestmotion value is not replayed as a new event on startup."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.motion_detectors[0]
    latest_motion_service = device.device_services[0]

    latest_motion_service._event_callbacks[device.id]()
    await hass.async_block_till_done()

    state = hass.states.get("event.motion_detector")
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.parametrize(
    "device_buckets",
    [{"motion_detectors": [motion_detector_device()]}],
    indirect=True,
)
async def test_motion_detector_unregisters_callback_on_unload(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Unloading the entity removes its LatestMotion callback registration."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.motion_detectors[0]
    latest_motion_service = device.device_services[0]
    assert device.id in latest_motion_service._event_callbacks

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert device.id not in latest_motion_service._event_callbacks


@pytest.mark.parametrize(
    "device_buckets",
    [{"motion_detectors2": [motion_detector2_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_motion_detector2_no_motion_yet(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A gen2 Motion Detector's event entity exists but has no state before a motion event fires."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("event.motion_detector")
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.parametrize(
    "device_buckets",
    [{"motion_detectors2": [motion_detector2_device()]}],
    indirect=True,
)
async def test_motion_detector2_fires_on_new_timestamp(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A LatestMotion push updates a gen2 event entity's state and attributes."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.motion_detectors2[0]
    latest_motion_service = device.device_services[0]

    device.latestmotion = "2026-09-25T12:00:00.000Z"
    latest_motion_service._event_callbacks[device.id]()
    await hass.async_block_till_done()

    state = hass.states.get("event.motion_detector")
    assert state is not None
    assert state.state != "unknown"
    assert state.attributes["event_type"] == "motion"
    assert state.attributes["last_time_triggered"] == "2026-09-25T12:00:00.000Z"


@pytest.mark.parametrize(
    "device_buckets",
    [{"smoke_detectors": [smoke_detector_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_smoke_detector_no_alarm_yet(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A Smoke Detector's event entity exists but has no state before an Alarm push."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("event.smoke_detector")
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.parametrize(
    "device_buckets",
    [{"smoke_detectors": [smoke_detector_device()]}],
    indirect=True,
)
async def test_smoke_detector_fires_on_alarm(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """An Alarm push updates the event entity's state to the new alarm state."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.smoke_detectors[0]
    alarm_service = device.device_services[0]

    device.alarmstate = AlarmService.State.PRIMARY_ALARM
    alarm_service._event_callbacks[device.id]()
    await hass.async_block_till_done()

    state = hass.states.get("event.smoke_detector")
    assert state is not None
    assert state.state != "unknown"
    assert state.attributes["event_type"] == "primary_alarm"


@pytest.mark.parametrize(
    "device_buckets",
    [{"smoke_detectors": [smoke_detector_device()]}],
    indirect=True,
)
async def test_smoke_detector_unregisters_callback_on_unload(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Unloading the entity removes its Alarm callback registration."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.smoke_detectors[0]
    alarm_service = device.device_services[0]
    assert device.id in alarm_service._event_callbacks

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert device.id not in alarm_service._event_callbacks
