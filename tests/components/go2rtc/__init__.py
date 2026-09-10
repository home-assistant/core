"""Go2rtc tests."""

from homeassistant.components.camera import (
    Camera,
    CameraEntityFeature,
    CameraStreamSource,
)


class MockCamera(Camera):
    """Mock Camera Entity."""

    _attr_supported_features: CameraEntityFeature = CameraEntityFeature.STREAM

    def __init__(self, unique_id: str | None, name: str = "Test") -> None:
        """Initialize the mock entity."""
        super().__init__()
        self._stream_source: str | None = "rtsp://stream"
        self._stream_sources: list[CameraStreamSource] | None = None
        self._attr_unique_id = unique_id
        self._attr_name = name

    def set_stream_source(self, stream_source: str | None) -> None:
        """Set the stream source."""
        self._stream_source = stream_source

    def set_stream_sources(self, stream_sources: list[CameraStreamSource]) -> None:
        """Set the stream sources."""
        self._stream_sources = stream_sources

    async def stream_source(self) -> str | None:
        """Return the source of the stream.

        This is used by cameras with CameraEntityFeature.STREAM
        and StreamType.HLS.
        """
        return self._stream_source

    async def async_get_stream_sources(self) -> list[CameraStreamSource]:
        """Return all sources of the stream."""
        if self._stream_sources is not None:
            return self._stream_sources.copy()
        return await super().async_get_stream_sources()

    @property
    def use_stream_for_stills(self) -> bool:
        """Always use the RTSP stream to generate snapshots."""
        return True
