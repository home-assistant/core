"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""

from unittest.mock import Mock

from homeassistant.components.camera import RtcConfiguration, WebRtcConfiguration

EMPTY_8_6_JPEG = b"empty_8_6"
WEBRTC_ANSWER = "a=sendonly"
WEBRTC_CONFIG = WebRtcConfiguration(
    rtc_configuration=RtcConfiguration(
        ice_servers=[RtcConfiguration.IceServer(urls="stun:stun.foobar.com")]
    ),
    audio_direction=WebRtcConfiguration.TransportDirection.SENDRECV,
)


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
