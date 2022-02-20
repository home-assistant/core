"""Axis conftest."""
from __future__ import annotations

from unittest.mock import patch

from axis.rtsp import (
    SIGNAL_DATA,
    SIGNAL_FAILED,
    SIGNAL_PLAYING,
    STATE_PLAYING,
    STATE_STOPPED,
)
import pytest

from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture(autouse=True)
def mock_axis_rtspclient():
    """No real RTSP communication allowed."""
    with patch("axis.streammanager.RTSPClient") as rtsp_client_mock:

        rtsp_client_mock.return_value.session.state = STATE_STOPPED

        async def start_stream():
            """Set state to playing when calling RTSPClient.start."""
            rtsp_client_mock.return_value.session.state = STATE_PLAYING

        rtsp_client_mock.return_value.start = start_stream

        def stop_stream():
            """Set state to stopped when calling RTSPClient.stop."""
            rtsp_client_mock.return_value.session.state = STATE_STOPPED

        rtsp_client_mock.return_value.stop = stop_stream

        def make_rtsp_call(data: dict | None = None, state: str = ""):
            """Generate a RTSP call."""
            axis_streammanager_session_callback = rtsp_client_mock.call_args[0][4]

            if data:
                rtsp_client_mock.return_value.rtp.data = data
                axis_streammanager_session_callback(signal=SIGNAL_DATA)
            elif state:
                axis_streammanager_session_callback(signal=state)
            else:
                raise NotImplementedError

        yield make_rtsp_call


@pytest.fixture(autouse=True)
def mock_rtsp_event(mock_axis_rtspclient):
    """Fixture to allow mocking received RTSP events."""

    def send_event(
        topic: str,
        data_type: str,
        data_value: str,
        operation: str = "Initialized",
        source_name: str = "",
        source_idx: str = "",
    ) -> None:
        source = ""
        if source_name != "" and source_idx != "":
            source = f'<tt:SimpleItem Name="{source_name}" Value="{source_idx}"/>'

        event = f"""<?xml version="1.0" encoding="UTF-8"?>
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">
    <tt:Event>
        <wsnt:NotificationMessage xmlns:tns1="http://www.onvif.org/ver10/topics"
                                  xmlns:tnsaxis="http://www.axis.com/2009/event/topics"
                                  xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2"
                                  xmlns:wsa5="http://www.w3.org/2005/08/addressing">
            <wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">
                {topic}
            </wsnt:Topic>
            <wsnt:ProducerReference>
                <wsa5:Address>
                    uri://bf32a3b9-e5e7-4d57-a48d-1b5be9ae7b16/ProducerReference
                </wsa5:Address>
            </wsnt:ProducerReference>
            <wsnt:Message>
                <tt:Message UtcTime="2020-11-03T20:21:48.346022Z"
                            PropertyOperation="{operation}">
                    <tt:Source>{source}</tt:Source>
                    <tt:Key></tt:Key>
                    <tt:Data>
                        <tt:SimpleItem Name="{data_type}" Value="{data_value}"/>
                    </tt:Data>
                </tt:Message>
            </wsnt:Message>
        </wsnt:NotificationMessage>
    </tt:Event>
</tt:MetadataStream>
"""

        mock_axis_rtspclient(data=event.encode("utf-8"))

    yield send_event


@pytest.fixture(autouse=True)
def mock_rtsp_signal_state(mock_axis_rtspclient):
    """Fixture to allow mocking RTSP state signalling."""

    def send_signal(connected: bool) -> None:
        """Signal state change of RTSP connection."""
        signal = SIGNAL_PLAYING if connected else SIGNAL_FAILED
        mock_axis_rtspclient(state=signal)

    yield send_signal
