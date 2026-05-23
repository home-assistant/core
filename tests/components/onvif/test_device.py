"""Tests for ONVIF device availability tracking and profile refresh."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.onvif.device import ONVIFDevice
from homeassistant.components.onvif.event_manager import EventManager
from homeassistant.components.onvif.models import Profile, Resolution, Video
from homeassistant.core import HomeAssistant

from . import HOST, MAC, NAME, PASSWORD, PORT, USERNAME

from tests.common import MockConfigEntry


def _make_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock ONVIF config entry."""
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
    return entry


def _make_device(hass: HomeAssistant, entry: MockConfigEntry) -> ONVIFDevice:
    """Create an ONVIFDevice with a mocked EventManager."""
    device = ONVIFDevice(hass, entry)
    device.profiles = [
        Profile(
            index=0,
            token="token_0",
            name="Profile 0",
            video=Video("H264", Resolution(1920, 1080)),
        ),
    ]
    # Create a real EventManager with onvif_device reference
    mock_onvif_camera = MagicMock()
    device.events = EventManager(
        hass, mock_onvif_camera, entry, NAME, onvif_device=device
    )
    return device


async def test_mark_available_from_unavailable(hass: HomeAssistant) -> None:
    """Test marking device available when it was unavailable."""
    entry = _make_config_entry(hass)
    device = _make_device(hass, entry)

    device.available = False
    device.async_mark_available()
    assert device.available is True


async def test_mark_available_when_already_available(
    hass: HomeAssistant,
) -> None:
    """Test marking device available when already available is a no-op."""
    entry = _make_config_entry(hass)
    device = _make_device(hass, entry)

    assert device.available is True
    device.async_mark_available()
    assert device.available is True


async def test_mark_unavailable_from_available(hass: HomeAssistant) -> None:
    """Test marking device unavailable when it was available."""
    entry = _make_config_entry(hass)
    device = _make_device(hass, entry)

    assert device.available is True
    device.async_mark_unavailable()
    assert device.available is False


async def test_mark_unavailable_when_already_unavailable(
    hass: HomeAssistant,
) -> None:
    """Test marking device unavailable when already unavailable is a no-op."""
    entry = _make_config_entry(hass)
    device = _make_device(hass, entry)

    device.available = False
    device.async_mark_unavailable()
    assert device.available is False


async def test_refresh_profiles_no_change(hass: HomeAssistant) -> None:
    """Test refresh profiles when profiles haven't changed does not reload."""
    entry = _make_config_entry(hass)
    device = _make_device(hass, entry)

    original_profiles = list(device.profiles)

    with patch.object(
        device, "async_get_profiles", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = original_profiles
        await device.async_refresh_profiles()

    assert device.profiles == original_profiles


async def test_refresh_profiles_with_change_triggers_reload(
    hass: HomeAssistant,
) -> None:
    """Test refresh profiles triggers reload when profile tokens changed."""
    entry = _make_config_entry(hass)
    device = _make_device(hass, entry)

    new_profile = Profile(
        index=0,
        token="new_token",
        name="New Profile",
        video=Video("H264", Resolution(1920, 1080)),
    )

    with (
        patch.object(
            device, "async_get_profiles", new_callable=AsyncMock
        ) as mock_get,
        patch.object(
            hass.config_entries, "async_reload", new_callable=AsyncMock
        ) as mock_reload,
    ):
        mock_get.return_value = [new_profile]
        await device.async_refresh_profiles()
        await hass.async_block_till_done()

    mock_reload.assert_called_once_with(entry.entry_id)
    assert device.profiles == [new_profile]


async def test_refresh_profiles_handles_timeout_error(
    hass: HomeAssistant,
) -> None:
    """Test refresh profiles gracefully handles timeout errors."""
    entry = _make_config_entry(hass)
    device = _make_device(hass, entry)

    original_profiles = list(device.profiles)

    with patch.object(
        device,
        "async_get_profiles",
        new_callable=AsyncMock,
        side_effect=TimeoutError("connection timeout"),
    ):
        await device.async_refresh_profiles()

    assert device.profiles == original_profiles


async def test_refresh_profiles_empty_result(hass: HomeAssistant) -> None:
    """Test refresh profiles does nothing when result is empty."""
    entry = _make_config_entry(hass)
    device = _make_device(hass, entry)

    original_profiles = list(device.profiles)

    with patch.object(
        device, "async_get_profiles", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = []
        await device.async_refresh_profiles()

    assert device.profiles == original_profiles
