"""Fixtures for Amcrest integration tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.amcrest import AmcrestDevice

CAMERA_NAME = "Test Camera"
SERIAL_NUMBER = "SN-TEST-12345"


class _MockAmcrestAPI:
    """Test double for AmcrestChecker.

    Async properties in the amcrest library are Python @property decorators on
    async def methods, so accessing them returns a coroutine rather than a
    coroutine function.  Using AsyncMock() directly for these would require
    calling the mock *and* awaiting the result, which doesn't match how the
    integration accesses them (``await api.some_prop`` with no parentheses).
    The @property pattern here replicates the real library behaviour.
    """

    available = True

    def __init__(self) -> None:
        """Set configurable values that tests can override directly."""
        # Configurable return values
        self.serial = SERIAL_NUMBER
        self.ptz_presets_count = 5
        self.storage_all: dict = {
            "total": (100.0, "GB"),
            "used": (50.0, "GB"),
            "used_percent": 50.0,
        }
        self.vendor: str | None = "Amcrest"
        self.device_type: str | None = "IP2M-841"
        self.record_mode = "Automatic"
        self.day_night_color = 0  # index 0 → "color"
        self.video_enabled = True
        self.motion_detector = False
        self.audio_enabled = False
        self.motion_recording = False
        self.privacy_mode = False
        self.event_channels: list[int] = []
        self.rtsp_url_value = "rtsp://192.168.1.100/live"
        # Map attribute name → exception to raise on access
        self._raise_on: dict[str, Exception] = {}

    def set_error(self, attr: str, exc: Exception) -> None:
        """Inject an exception to be raised when *attr* is next accessed."""
        self._raise_on[attr] = exc

    def _value_or_raise(self, attr: str, value):
        if attr in self._raise_on:
            raise self._raise_on[attr]
        return value

    # ── Async properties ─────────────────────────────────────────────────────
    # Each returns a fresh coroutine so multiple awaits work correctly.

    @property
    def async_serial_number(self):
        async def _():
            return self._value_or_raise("serial_number", self.serial)

        return _()

    @property
    def async_ptz_presets_count(self):
        async def _():
            return self._value_or_raise("ptz_presets_count", self.ptz_presets_count)

        return _()

    @property
    def async_storage_all(self):
        async def _():
            return self._value_or_raise("storage_all", self.storage_all)

        return _()

    @property
    def async_current_time(self):
        async def _():
            return self._value_or_raise("current_time", "2024-01-01T00:00:00")

        return _()

    @property
    def async_vendor_information(self):
        async def _():
            return self._value_or_raise("vendor_information", self.vendor)

        return _()

    @property
    def async_device_type(self):
        async def _():
            return self._value_or_raise("device_type", self.device_type)

        return _()

    @property
    def async_record_mode(self):
        async def _():
            return self._value_or_raise("record_mode", self.record_mode)

        return _()

    @property
    def async_day_night_color(self):
        async def _():
            return self._value_or_raise("day_night_color", self.day_night_color)

        return _()

    # ── Async methods ─────────────────────────────────────────────────────────

    async def async_privacy_config(self) -> str:
        if "privacy_config" in self._raise_on:
            raise self._raise_on["privacy_config"]
        mode = "true" if self.privacy_mode else "false"
        return f"table.LeLensMask[0].Enable={mode}\nfoo=bar"

    async def async_event_channels_happened(self, eventcode: str) -> list[int]:
        if "event_channels_happened" in self._raise_on:
            raise self._raise_on["event_channels_happened"]
        return self.event_channels

    async def async_rtsp_url(self, *, channel: int = 1, typeno: int = 0) -> str:
        return self.rtsp_url_value

    async def async_is_video_enabled(self, channel: int, stream: str) -> bool:
        return self.video_enabled

    async def async_is_motion_detector_on(self, *, channel: int = 0) -> bool:
        return self.motion_detector

    async def async_is_audio_enabled(self, channel: int, stream: str) -> bool:
        return self.audio_enabled

    async def async_is_record_on_motion_detection(self) -> bool:
        return self.motion_recording


@pytest.fixture
def mock_store() -> MagicMock:
    """Patch Store to avoid disk I/O, starting with no prior stored data."""
    with patch("homeassistant.components.amcrest.Store") as mock_cls:
        instance = MagicMock()
        mock_cls.return_value = instance
        instance.async_load = AsyncMock(return_value=None)
        instance.async_save = AsyncMock()
        yield instance


@pytest.fixture
def mock_event_monitor() -> None:
    """Patch _start_event_monitor to prevent daemon thread creation."""
    with patch("homeassistant.components.amcrest._start_event_monitor"):
        yield


@pytest.fixture
def mock_discovery() -> None:
    """Patch discovery.async_load_platform to prevent platform loading."""
    with patch(
        "homeassistant.helpers.discovery.async_load_platform",
        new_callable=AsyncMock,
    ):
        yield


@pytest.fixture
def mock_api() -> _MockAmcrestAPI:
    """Return a fresh _MockAmcrestAPI for each test."""
    return _MockAmcrestAPI()


@pytest.fixture
def device(mock_api: _MockAmcrestAPI) -> AmcrestDevice:
    """AmcrestDevice backed by the mock API with a known serial number."""
    return AmcrestDevice(
        api=mock_api,
        authentication=None,
        ffmpeg_arguments=["-pred", "1"],
        stream_source="snapshot",
        resolution=0,
        control_light=True,
        serial_number=SERIAL_NUMBER,
    )
