"""Tests for ONVIF EventManager availability tracking via PullPoint heartbeat."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.onvif.device import ONVIFDevice
from homeassistant.components.onvif.event_manager import EventManager
from homeassistant.components.onvif.models import Profile, Resolution, Video
from homeassistant.core import HomeAssistant

from . import HOST, MAC, NAME, PASSWORD, PORT, USERNAME

from tests.common import MockConfigEntry


def _make_event_manager(hass: HomeAssistant) -> tuple[EventManager, ONVIFDevice]:
    """Create an EventManager with a real ONVIFDevice for testing."""
    entry = MockConfigEntry(
        domain="onvif",
        data={
            "name": NAME,
            "host": HOST,
            "port": PORT,
            "username": USERNAME,
            "password": PASSWORD,
        },
        options={},
        entry_id="test_entry",
        unique_id=MAC,
    )
    entry.add_to_hass(hass)

    device = ONVIFDevice(hass, entry)
    device.profiles = [
        Profile(
            index=0,
            token="token_0",
            name="Profile 0",
            video=Video("H264", Resolution(1920, 1080)),
        ),
    ]

    mock_onvif_camera = MagicMock()
    event_manager = EventManager(
        hass, mock_onvif_camera, entry, NAME, onvif_device=device
    )
    device.events = event_manager
    return event_manager, device


async def test_pull_failed_marks_unavailable_after_threshold(
    hass: HomeAssistant,
) -> None:
    """Test that 3 consecutive pull failures mark device unavailable."""
    event_manager, device = _make_event_manager(hass)

    assert device.available is True

    event_manager.async_event_pull_failed()
    assert device.available is True

    event_manager.async_event_pull_failed()
    assert device.available is True

    event_manager.async_event_pull_failed()
    assert device.available is False


async def test_pull_failed_stays_unavailable(hass: HomeAssistant) -> None:
    """Test that additional failures after threshold keep device unavailable."""
    event_manager, device = _make_event_manager(hass)

    for _ in range(5):
        event_manager.async_event_pull_failed()

    assert device.available is False
    assert event_manager._consecutive_errors == 5


async def test_pull_success_resets_error_counter(hass: HomeAssistant) -> None:
    """Test that a successful pull resets the consecutive error counter."""
    event_manager, device = _make_event_manager(hass)

    event_manager.async_event_pull_failed()
    event_manager.async_event_pull_failed()
    assert event_manager._consecutive_errors == 2

    event_manager.async_event_pull_success()
    assert event_manager._consecutive_errors == 0
    assert device.available is True


async def test_pull_success_restores_availability(hass: HomeAssistant) -> None:
    """Test that success after unavailable restores availability and refreshes profiles."""
    event_manager, device = _make_event_manager(hass)

    # Make device unavailable
    for _ in range(3):
        event_manager.async_event_pull_failed()
    assert device.available is False

    with patch.object(
        device, "async_refresh_profiles", new_callable=AsyncMock
    ) as mock_refresh:
        event_manager.async_event_pull_success()
        await hass.async_block_till_done()

    assert device.available is True
    assert event_manager._consecutive_errors == 0
    mock_refresh.assert_called_once()


async def test_pull_success_no_refresh_when_already_available(
    hass: HomeAssistant,
) -> None:
    """Test that success when already available does not trigger profile refresh."""
    event_manager, device = _make_event_manager(hass)

    assert device.available is True

    with patch.object(
        device, "async_refresh_profiles", new_callable=AsyncMock
    ) as mock_refresh:
        event_manager.async_event_pull_success()
        await hass.async_block_till_done()

    mock_refresh.assert_not_called()


async def test_pull_failed_without_onvif_device(hass: HomeAssistant) -> None:
    """Test that event_pull_failed works without onvif_device (backward compat)."""
    entry = MockConfigEntry(
        domain="onvif",
        data={
            "name": NAME,
            "host": HOST,
            "port": PORT,
            "username": USERNAME,
            "password": PASSWORD,
        },
        options={},
        entry_id="test_entry",
        unique_id=MAC,
    )
    entry.add_to_hass(hass)

    mock_onvif_camera = MagicMock()
    event_manager = EventManager(hass, mock_onvif_camera, entry, NAME)

    # Should not raise even without onvif_device
    for _ in range(5):
        event_manager.async_event_pull_failed()
    event_manager.async_event_pull_success()

    assert event_manager._consecutive_errors == 0


async def test_pull_success_without_onvif_device(hass: HomeAssistant) -> None:
    """Test that event_pull_success works without onvif_device (backward compat)."""
    entry = MockConfigEntry(
        domain="onvif",
        data={
            "name": NAME,
            "host": HOST,
            "port": PORT,
            "username": USERNAME,
            "password": PASSWORD,
        },
        options={},
        entry_id="test_entry",
        unique_id=MAC,
    )
    entry.add_to_hass(hass)

    mock_onvif_camera = MagicMock()
    event_manager = EventManager(hass, mock_onvif_camera, entry, NAME)

    # Should not raise
    event_manager.async_event_pull_success()
    assert event_manager._consecutive_errors == 0
