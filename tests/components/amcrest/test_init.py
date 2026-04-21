"""Test the Amcrest integration init."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.amcrest.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_config_entry_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_amcrest_api: MagicMock,
) -> None:
    """Test setting up and unloading a config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.amcrest.AmcrestChecker", return_value=mock_amcrest_api
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Test unloading
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is not ConfigEntryState.LOADED


async def test_device_registry_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_amcrest_api: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that device is registered properly."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.amcrest.AmcrestChecker", return_value=mock_amcrest_api
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify device is registered with serial number identifier
    device = device_registry.async_get_device(identifiers={(DOMAIN, "ABCD1234567890")})
    assert device is not None
    assert device.name == "Living Room"
    assert device.manufacturer == "Amcrest"
    assert device.configuration_url == "http://192.168.1.100"

    # Check additional identifier when serial is available
    device_with_serial = device_registry.async_get_device(
        identifiers={(DOMAIN, "ABCD1234567890")}
    )
    # Should be the same device due to multiple identifiers
    assert device_with_serial is not None
    assert device_with_serial.id == device.id


async def test_device_registry_creation_no_serial(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that device is registered properly when serial is not available."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.amcrest.AmcrestChecker") as mock_api_class:
        mock_api = mock_api_class.return_value

        # For async properties, we need to return new coroutines each time they're accessed
        def make_async_property(return_value):
            """Create a property that returns a fresh coroutine each time."""

            async def async_func():
                return return_value

            def property_getter(*args, **kwargs):
                return async_func()

            return property(property_getter)

        # Set up async properties with empty serial number
        type(mock_api).async_serial_number = make_async_property("")
        type(mock_api).async_vendor_information = make_async_property("Amcrest")
        type(mock_api).async_device_type = make_async_property("IP Camera")
        type(mock_api).async_current_time = make_async_property("2023-01-01 12:00:00")
        type(mock_api).async_record_mode = make_async_property("Manual")
        type(mock_api).async_day_night_color = make_async_property(1)
        type(mock_api).async_ptz_presets_count = make_async_property(5)
        type(mock_api).async_storage_all = make_async_property(
            {
                "total": [64.0, "GB"],
                "used": [12.5, "GB"],
                "used_percent": 19.53,
            }
        )

        # Async methods
        mock_api.async_privacy_config = AsyncMock(
            return_value="Privacy.Enabled=true\nPrivacy.Enabled[1]=false"
        )
        mock_api.async_rtsp_url = AsyncMock(
            return_value="rtsp://192.168.1.100:554/cam/realmonitor?channel=1&subtype=0"
        )
        mock_api.async_is_video_enabled = AsyncMock(return_value=True)
        mock_api.async_is_motion_detector_on = AsyncMock(return_value=True)
        mock_api.async_is_audio_enabled = AsyncMock(return_value=True)
        mock_api.async_is_record_on_motion_detection = AsyncMock(return_value=True)
        mock_api.async_event_channels_happened = AsyncMock(return_value=False)

        mock_api.get_base_url = MagicMock(return_value="http://192.168.1.100")

        # Synchronous properties
        mock_api.available = True
        mock_api.serial_number = MagicMock(return_value="")  # Empty serial number

        # Available flag for legacy support
        mock_api.async_available_flag = AsyncMock()
        mock_api.async_available_flag.is_set.return_value = True

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify device is registered with only config entry ID
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert device is not None
    assert device.name == "Living Room"
    assert device.manufacturer == "Amcrest"


async def test_config_entry_not_ready_on_api_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that config entry setup fails when API is unavailable."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.amcrest.AmcrestChecker",
        side_effect=Exception("Connection failed"),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_platforms_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_amcrest_api: MagicMock,
) -> None:
    """Test that the expected platforms are loaded."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.amcrest.AmcrestChecker", return_value=mock_amcrest_api
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Check that camera platform is loaded
    camera_entities = hass.states.async_entity_ids("camera")
    assert len(camera_entities) >= 1

    # Binary sensor platform is loaded conditionally based on available sensors
