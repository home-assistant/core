"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""

from unittest.mock import Mock

from webrtc_models import RTCIceCandidateInit

from homeassistant.components.camera import (
    Camera,
    CameraWebRTCProvider,
    WebRTCAnswer,
    WebRTCSendMessage,
)
from homeassistant.core import callback

EMPTY_8_6_JPEG = b"empty_8_6"
WEBRTC_ANSWER = "a=sendonly"
STREAM_SOURCE = "rtsp://127.0.0.1/stream"


def mock_turbo_jpeg(
    first_width=None, second_width=None, first_height=None, second_height=None
):
    """Mock a TurboJPEG instance."""
    mocked_turbo_jpeg = Mock()
    mocked_turbo_jpeg.decode_header.side_effect = [
        (first_width, first_height, 0, 0),
        (second_width, second_height, 0, 0),
    ]
    mocked_turbo_jpeg.scale_with_quality.return_value = EMPTY_8_6_JPEG
    mocked_turbo_jpeg.encode.return_value = EMPTY_8_6_JPEG
    return mocked_turbo_jpeg


class SomeTestProvider(CameraWebRTCProvider):
    """Test provider."""

    def __init__(self) -> None:
        """Initialize the provider."""
        self._is_supported = True

    @property
    def domain(self) -> str:
        """Return the integration domain of the provider."""
        return "some_test"

    @callback
    def async_is_supported(self, stream_source: str) -> bool:
        """Determine if the provider supports the stream source."""
        return self._is_supported

    async def async_handle_async_webrtc_offer(
        self,
        camera: Camera,
        offer_sdp: str,
        session_id: str,
        send_message: WebRTCSendMessage,
    ) -> None:
        """Handle the WebRTC offer and return the answer via the provided callback.

        Return value determines if the offer was handled successfully.
        """
        send_message(WebRTCAnswer(answer="answer"))

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Handle the WebRTC candidate."""

    @callback
    def async_close_session(self, session_id: str) -> None:
        """Close the session."""
