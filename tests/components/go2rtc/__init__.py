"""Go2rtc tests."""

from homeassistant.components.camera import Camera, CameraEntityFeature


class MockCamera(Camera):
    """Mock Camera Entity."""

    _attr_supported_features: CameraEntityFeature = CameraEntityFeature.STREAM

    def __init__(self, unique_id: str | None, name: str = "Test") -> None:
        """Initialize the mock entity."""
        super().__init__()
        self._stream_source: str | None = "rtsp://stream"
        self._additional_stream_sources: list[str] = []
        self._attr_unique_id = unique_id
        self._attr_name = name

    def set_stream_source(self, stream_source: str | None) -> None:
        """Set the stream source."""
        self._stream_source = stream_source

    def set_additional_stream_sources(self, sources: list[str]) -> None:
        """Set the additional stream sources."""
        self._additional_stream_sources = sources

    async def stream_source(self) -> str | None:
        """Return the source of the stream.

        This is used by cameras with CameraEntityFeature.STREAM
        and StreamType.HLS.
        """
        return self._stream_source

    async def additional_stream_sources(self) -> list[str]:
        """Return additional sources to combine with the stream source."""
        return self._additional_stream_sources

    @property
    def use_stream_for_stills(self) -> bool:
        """Always use the RTSP stream to generate snapshots."""
        return True
