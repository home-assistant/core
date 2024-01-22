"""Axis conftest."""
from __future__ import annotations

from collections.abc import Generator
from copy import deepcopy
from unittest.mock import AsyncMock, patch

from axis.rtsp import Signal, State
import pytest
import respx

from homeassistant.components.axis.const import CONF_EVENTS, DOMAIN as AXIS_DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_MODEL,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)

from .const import (
    API_DISCOVERY_RESPONSE,
    APPLICATIONS_LIST_RESPONSE,
    BASIC_DEVICE_INFO_RESPONSE,
    BRAND_RESPONSE,
    DEFAULT_HOST,
    FORMATTED_MAC,
    IMAGE_RESPONSE,
    MODEL,
    MQTT_CLIENT_RESPONSE,
    NAME,
    PORT_MANAGEMENT_RESPONSE,
    PORTS_RESPONSE,
    PROPERTIES_RESPONSE,
    PTZ_RESPONSE,
    STREAM_PROFILES_RESPONSE,
    VIEW_AREAS_RESPONSE,
    VMD4_RESPONSE,
)

from tests.common import MockConfigEntry
from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.axis.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


# Config entry fixtures


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config, options, config_entry_version):
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=AXIS_DOMAIN,
        entry_id="676abe5b73621446e6550a2e86ffe3dd",
        unique_id=FORMATTED_MAC,
        data=config,
        options=options,
        version=config_entry_version,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config_entry_version")
def config_entry_version_fixture(request):
    """Define a config entry version fixture."""
    return 3


@pytest.fixture(name="config")
def config_fixture():
    """Define a config entry data fixture."""
    return {
        CONF_HOST: DEFAULT_HOST,
        CONF_USERNAME: "root",
        CONF_PASSWORD: "pass",
        CONF_PORT: 80,
        CONF_MODEL: MODEL,
        CONF_NAME: NAME,
    }


@pytest.fixture(name="options")
def options_fixture(request):
    """Define a config entry options fixture."""
    return {CONF_EVENTS: True}


# Axis API fixtures


@pytest.fixture(name="mock_vapix_requests")
def default_request_fixture(respx_mock):
    """Mock default Vapix requests responses."""

    def __mock_default_requests(host):
        path = f"http://{host}:80"

        if host != DEFAULT_HOST:
            respx.post(f"{path}/axis-cgi/apidiscovery.cgi").respond(
                json=API_DISCOVERY_RESPONSE,
            )
        respx.post(f"{path}/axis-cgi/basicdeviceinfo.cgi").respond(
            json=BASIC_DEVICE_INFO_RESPONSE,
        )
        respx.post(f"{path}/axis-cgi/io/portmanagement.cgi").respond(
            json=PORT_MANAGEMENT_RESPONSE,
        )
        respx.post(f"{path}/axis-cgi/mqtt/client.cgi").respond(
            json=MQTT_CLIENT_RESPONSE,
        )
        respx.post(f"{path}/axis-cgi/streamprofile.cgi").respond(
            json=STREAM_PROFILES_RESPONSE,
        )
        respx.post(f"{path}/axis-cgi/viewarea/info.cgi").respond(
            json=VIEW_AREAS_RESPONSE
        )
        respx.get(f"{path}/axis-cgi/param.cgi?action=list&group=root.Brand").respond(
            text=BRAND_RESPONSE,
            headers={"Content-Type": "text/plain"},
        )
        respx.get(f"{path}/axis-cgi/param.cgi?action=list&group=root.Image").respond(
            text=IMAGE_RESPONSE,
            headers={"Content-Type": "text/plain"},
        )
        respx.get(f"{path}/axis-cgi/param.cgi?action=list&group=root.Input").respond(
            text=PORTS_RESPONSE,
            headers={"Content-Type": "text/plain"},
        )
        respx.get(f"{path}/axis-cgi/param.cgi?action=list&group=root.IOPort").respond(
            text=PORTS_RESPONSE,
            headers={"Content-Type": "text/plain"},
        )
        respx.get(f"{path}/axis-cgi/param.cgi?action=list&group=root.Output").respond(
            text=PORTS_RESPONSE,
            headers={"Content-Type": "text/plain"},
        )
        respx.get(
            f"{path}/axis-cgi/param.cgi?action=list&group=root.Properties"
        ).respond(
            text=PROPERTIES_RESPONSE,
            headers={"Content-Type": "text/plain"},
        )
        respx.get(f"{path}/axis-cgi/param.cgi?action=list&group=root.PTZ").respond(
            text=PTZ_RESPONSE,
            headers={"Content-Type": "text/plain"},
        )
        respx.get(
            f"{path}/axis-cgi/param.cgi?action=list&group=root.StreamProfile"
        ).respond(
            text=STREAM_PROFILES_RESPONSE,
            headers={"Content-Type": "text/plain"},
        )
        respx.post(f"{path}/axis-cgi/applications/list.cgi").respond(
            text=APPLICATIONS_LIST_RESPONSE,
            headers={"Content-Type": "text/xml"},
        )
        respx.post(f"{path}/local/vmd/control.cgi").respond(json=VMD4_RESPONSE)

    return __mock_default_requests


@pytest.fixture
def api_discovery_items():
    """Additional Apidiscovery items."""
    return {}


@pytest.fixture(autouse=True)
def api_discovery_fixture(api_discovery_items):
    """Apidiscovery mock response."""
    data = deepcopy(API_DISCOVERY_RESPONSE)
    if api_discovery_items:
        data["data"]["apiList"].append(api_discovery_items)
    respx.post(f"http://{DEFAULT_HOST}:80/axis-cgi/apidiscovery.cgi").respond(json=data)


@pytest.fixture(name="setup_default_vapix_requests")
def default_vapix_requests_fixture(mock_vapix_requests):
    """Mock default Vapix requests responses."""
    mock_vapix_requests(DEFAULT_HOST)


@pytest.fixture(name="prepare_config_entry")
async def prep_config_entry_fixture(hass, config_entry, setup_default_vapix_requests):
    """Fixture factory to set up Axis network device."""

    async def __mock_setup_config_entry():
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        return config_entry

    return __mock_setup_config_entry


@pytest.fixture(name="setup_config_entry")
async def setup_config_entry_fixture(hass, config_entry, setup_default_vapix_requests):
    """Define a fixture to set up Axis network device."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


# RTSP fixtures


@pytest.fixture(autouse=True)
def mock_axis_rtspclient():
    """No real RTSP communication allowed."""
    with patch("axis.stream_manager.RTSPClient") as rtsp_client_mock:
        rtsp_client_mock.return_value.session.state = State.STOPPED

        async def start_stream():
            """Set state to playing when calling RTSPClient.start."""
            rtsp_client_mock.return_value.session.state = State.PLAYING

        rtsp_client_mock.return_value.start = start_stream

        def stop_stream():
            """Set state to stopped when calling RTSPClient.stop."""
            rtsp_client_mock.return_value.session.state = State.STOPPED

        rtsp_client_mock.return_value.stop = stop_stream

        def make_rtsp_call(data: dict | None = None, state: str = ""):
            """Generate a RTSP call."""
            axis_streammanager_session_callback = rtsp_client_mock.call_args[0][4]

            if data:
                rtsp_client_mock.return_value.rtp.data = data
                axis_streammanager_session_callback(signal=Signal.DATA)
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

    return send_event


@pytest.fixture(autouse=True)
def mock_rtsp_signal_state(mock_axis_rtspclient):
    """Fixture to allow mocking RTSP state signalling."""

    def send_signal(connected: bool) -> None:
        """Signal state change of RTSP connection."""
        signal = Signal.PLAYING if connected else Signal.FAILED
        mock_axis_rtspclient(state=signal)

    return send_signal
