"""Fixtures for component test."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def device_registry(hass: HomeAssistant):
    """Return an empty device registry."""
    return dr.async_get(hass)


@pytest.fixture
def entity_registry(hass: HomeAssistant):
    """Return an empty entity registry."""
    return er.async_get(hass)


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    return MockConfigEntry(
        domain="amcrest",
        title="Living Room",
        data={
            "host": "192.168.1.100",
            "name": "Living Room",
            "username": "admin",
            "password": "password",
            "port": 80,
            "rtsp_port": 554,
            "stream_source": "snapshot",
        },
        unique_id="ABCD1234567890",
    )


@pytest.fixture
def mock_amcrest_api():
    """Mock an AmcrestChecker instance."""
    mock_device = MagicMock()

    # For async properties, we need to return new coroutines each time they're accessed
    def make_async_property(return_value):
        """Create a property that returns a fresh coroutine each time."""

        async def async_func():
            return return_value

        def property_getter(*args, **kwargs):
            return async_func()

        return property(property_getter)

    # Set up async properties (accessed without parentheses)
    type(mock_device).async_serial_number = make_async_property("ABCD1234567890")
    type(mock_device).async_vendor_information = make_async_property("Amcrest")
    type(mock_device).async_device_type = make_async_property("IP Camera")
    type(mock_device).async_current_time = make_async_property("2023-01-01 12:00:00")
    type(mock_device).async_record_mode = make_async_property("Manual")
    type(mock_device).async_day_night_color = make_async_property(1)  # Index for "auto"
    type(mock_device).async_ptz_presets_count = make_async_property(5)
    type(mock_device).async_storage_all = make_async_property(
        {
            "total": [64.0, "GB"],
            "used": [12.5, "GB"],
            "used_percent": 19.53,
        }
    )

    # Async methods (called with parentheses and/or parameters)
    mock_device.async_privacy_config = AsyncMock(
        return_value="Privacy.Enabled=true\nPrivacy.Enabled[1]=false"
    )
    mock_device.async_rtsp_url = AsyncMock(
        return_value="rtsp://192.168.1.100:554/cam/realmonitor?channel=1&subtype=0"
    )
    mock_device.async_is_video_enabled = AsyncMock(return_value=True)
    mock_device.async_is_motion_detector_on = AsyncMock(return_value=True)
    mock_device.async_is_audio_enabled = AsyncMock(return_value=True)
    mock_device.async_is_record_on_motion_detection = AsyncMock(return_value=True)
    mock_device.async_event_channels_happened = AsyncMock(return_value=False)

    mock_device.get_base_url = MagicMock(return_value="http://192.168.1.100")
    # Synchronous properties
    mock_device.available = True
    mock_device.serial_number = MagicMock(return_value="ABCD1234567890")

    # Available flag for legacy support
    mock_device.async_available_flag = AsyncMock()
    mock_device.async_available_flag.is_set.return_value = True

    return mock_device


@pytest.fixture
def amcrest_device():
    """Mock an AmcrestChecker."""
    with patch("homeassistant.components.amcrest.AmcrestChecker") as mock:
        mock_device = MagicMock()

        # For async properties, we need to return new coroutines each time they're accessed
        def make_async_property(return_value):
            """Create a property that returns a fresh coroutine each time."""

            async def async_func():
                return return_value

            def property_getter(*args, **kwargs):
                return async_func()

            return property(property_getter)

        # Set up async properties (accessed without parentheses)
        type(mock_device).async_serial_number = make_async_property("ABCD1234567890")
        type(mock_device).async_vendor_information = make_async_property("Amcrest")
        type(mock_device).async_device_type = make_async_property("IP Camera")
        type(mock_device).async_current_time = make_async_property(
            "2023-01-01 12:00:00"
        )
        type(mock_device).async_record_mode = make_async_property("Manual")
        type(mock_device).async_day_night_color = make_async_property(
            1
        )  # Index for "auto"
        type(mock_device).async_ptz_presets_count = make_async_property(5)
        type(mock_device).async_storage_all = make_async_property(
            {
                "total": [64.0, "GB"],
                "used": [12.5, "GB"],
                "used_percent": 19.53,
            }
        )

        # Async methods (called with parentheses and/or parameters)
        mock_device.async_privacy_config = AsyncMock(
            return_value="Privacy.Enabled=true\nPrivacy.Enabled[1]=false"
        )
        mock_device.async_rtsp_url = AsyncMock(
            return_value="rtsp://192.168.1.100:554/cam/realmonitor?channel=1&subtype=0"
        )
        mock_device.async_is_video_enabled = AsyncMock(return_value=True)
        mock_device.async_is_motion_detector_on = AsyncMock(return_value=True)
        mock_device.async_is_audio_enabled = AsyncMock(return_value=True)
        mock_device.async_is_record_on_motion_detection = AsyncMock(return_value=True)
        mock_device.async_event_channels_happened = AsyncMock(return_value=False)

        # Synchronous properties
        mock_device.available = True
        mock_device.serial_number = MagicMock(return_value="ABCD1234567890")

        # Available flag for legacy support
        mock_device.async_available_flag = AsyncMock()
        mock_device.async_available_flag.is_set.return_value = True

        mock.return_value = mock_device
        yield mock_device
