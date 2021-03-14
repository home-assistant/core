"""Axis conftest."""

from typing import Optional
from unittest.mock import patch

from axis.rtsp import SIGNAL_DATA, STATE_PLAYING, STATE_STOPPED
import pytest

from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture(autouse=True)
def mock_axis_rtspclient():
    """No real RTSP communication allowed."""
    with patch("axis.streammanager.RTSPClient") as mock:

        mock.return_value.session.state = STATE_STOPPED

        async def start_stream():
            """Set state to playing when calling RTSPClient.start."""
            mock.return_value.session.state = STATE_PLAYING

        mock.return_value.start = start_stream

        def stop_stream():
            """Set state to stopped when calling RTSPClient.stop."""
            mock.return_value.session.state = STATE_STOPPED

        mock.return_value.stop = stop_stream

        def make_rtsp_call(data: Optional[dict] = None, state: str = ""):
            """Generate a rtsp call."""
            axis_streammanager_session_callback = mock.call_args[0][4]

            if data:
                mock.return_value.rtp.data = data
                axis_streammanager_session_callback(signal=SIGNAL_DATA)
            elif state:
                axis_streammanager_session_callback(signal=state)
            else:
                raise NotImplementedError

        yield make_rtsp_call
