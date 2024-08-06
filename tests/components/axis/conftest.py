"""Axis conftest."""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Generator
from copy import deepcopy
from types import MappingProxyType
from typing import Any, Protocol
from unittest.mock import AsyncMock, patch

from axis.rtsp import Signal, State
import pytest
import respx

from homeassistant.components.axis.const import DOMAIN as AXIS_DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_MODEL,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from .const import (
    API_DISCOVERY_RESPONSE,
    APP_AOA_RESPONSE,
    APP_VMD4_RESPONSE,
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
)

from tests.common import MockConfigEntry

type ConfigEntryFactoryType = Callable[[], Coroutine[Any, Any, MockConfigEntry]]
type RtspStateType = Callable[[bool], None]


class RtspEventMock(Protocol):
    """Fixture to allow mocking received RTSP events."""

    def __call__(
        self,
        topic: str,
        data_type: str,
        data_value: str,
        operation: str = "Initialized",
        source_name: str = "",
        source_idx: str = "",
    ) -> None:
        """Send RTSP event."""


class _RtspClientMock(Protocol):
    async def __call__(
        self, data: dict[str, Any] | None = None, state: str = ""
    ) -> None: ...


@pytest.fixture(name="mock_setup_entry")
def fixture_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.axis.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


# Config entry fixtures


@pytest.fixture(name="config_entry")
def fixture_config_entry(
    config_entry_data: MappingProxyType[str, Any],
    config_entry_options: MappingProxyType[str, Any],
    config_entry_version: int,
) -> MockConfigEntry:
    """Define a config entry fixture."""
    return MockConfigEntry(
        domain=AXIS_DOMAIN,
        entry_id="676abe5b73621446e6550a2e86ffe3dd",
        unique_id=FORMATTED_MAC,
        data=config_entry_data,
        options=config_entry_options,
        version=config_entry_version,
    )


@pytest.fixture(name="config_entry_version")
def fixture_config_entry_version() -> int:
    """Define a config entry version fixture."""
    return 3


@pytest.fixture(name="config_entry_data")
def fixture_config_entry_data() -> MappingProxyType[str, Any]:
    """Define a config entry data fixture."""
    return {
        CONF_HOST: DEFAULT_HOST,
        CONF_USERNAME: "root",
        CONF_PASSWORD: "pass",
        CONF_PORT: 80,
        CONF_MODEL: MODEL,
        CONF_NAME: NAME,
    }


@pytest.fixture(name="config_entry_options")
def fixture_config_entry_options() -> MappingProxyType[str, Any]:
    """Define a config entry options fixture."""
    return {}


# Axis API fixtures


@pytest.fixture(autouse=True)
def reset_mock_requests() -> Generator[None]:
    """Reset respx mock routes after the test."""
    yield
    respx.mock.clear()


@pytest.fixture(name="mock_requests")
def fixture_request(
    respx_mock: respx.MockRouter,
    port_management_payload: dict[str, Any],
    param_properties_payload: str,
    param_ports_payload: str,
    mqtt_status_code: int,
) -> Callable[[str], None]:
    """Mock default Vapix requests responses."""

    def __mock_default_requests(host: str) -> None:
        respx_mock(base_url=f"http://{host}:80")

        if host != DEFAULT_HOST:
            respx.post("/axis-cgi/apidiscovery.cgi").respond(
                json=API_DISCOVERY_RESPONSE,
            )
        respx.post("/axis-cgi/basicdeviceinfo.cgi").respond(
            json=BASIC_DEVICE_INFO_RESPONSE,
        )
        respx.post("/axis-cgi/io/portmanagement.cgi").respond(
            json=port_management_payload,
        )
        respx.post("/axis-cgi/mqtt/client.cgi").respond(
            json=MQTT_CLIENT_RESPONSE, status_code=mqtt_status_code
        )
        respx.post("/axis-cgi/streamprofile.cgi").respond(
            json=STREAM_PROFILES_RESPONSE,
        )
        respx.post("/axis-cgi/viewarea/info.cgi").respond(json=VIEW_AREAS_RESPONSE)
        respx.post(
            "/axis-cgi/param.cgi",
            data={"action": "list", "group": "root.Brand"},
        ).respond(
            text=BRAND_RESPONSE,
            headers={"Content-Type": "text/plain"},
        )
        respx.post(
            "/axis-cgi/param.cgi",
            data={"action": "list", "group": "root.Image"},
        ).respond(
            text=IMAGE_RESPONSE,
            headers={"Content-Type": "text/plain"},
        )
        respx.post(
            "/axis-cgi/param.cgi",
            data={"action": "list", "group": "root.Input"},
        ).respond(
            text=PORTS_RESPONSE,
            headers={"Content-Type": "text/plain"},
        )
        respx.post(
            "/axis-cgi/param.cgi",
            data={"action": "list", "group": "root.IOPort"},
        ).respond(
            text=param_ports_payload,
            headers={"Content-Type": "text/plain"},
        )
        respx.post(
            "/axis-cgi/param.cgi",
            data={"action": "list", "group": "root.Output"},
        ).respond(
            text=PORTS_RESPONSE,
            headers={"Content-Type": "text/plain"},
        )
        respx.post(
            "/axis-cgi/param.cgi",
            data={"action": "list", "group": "root.Properties"},
        ).respond(
            text=param_properties_payload,
            headers={"Content-Type": "text/plain"},
        )
        respx.post(
            "/axis-cgi/param.cgi",
            data={"action": "list", "group": "root.PTZ"},
        ).respond(
            text=PTZ_RESPONSE,
            headers={"Content-Type": "text/plain"},
        )
        respx.post(
            "/axis-cgi/param.cgi",
            data={"action": "list", "group": "root.StreamProfile"},
        ).respond(
            text=STREAM_PROFILES_RESPONSE,
            headers={"Content-Type": "text/plain"},
        )
        respx.post("/axis-cgi/applications/list.cgi").respond(
            text=APPLICATIONS_LIST_RESPONSE,
            headers={"Content-Type": "text/xml"},
        )
        respx.post("/local/fenceguard/control.cgi").respond(json=APP_VMD4_RESPONSE)
        respx.post("/local/loiteringguard/control.cgi").respond(json=APP_VMD4_RESPONSE)
        respx.post("/local/motionguard/control.cgi").respond(json=APP_VMD4_RESPONSE)
        respx.post("/local/vmd/control.cgi").respond(json=APP_VMD4_RESPONSE)
        respx.post("/local/objectanalytics/control.cgi").respond(json=APP_AOA_RESPONSE)

    return __mock_default_requests


@pytest.fixture
def api_discovery_items() -> dict[str, Any]:
    """Additional Apidiscovery items."""
    return {}


@pytest.fixture(autouse=True)
def fixture_api_discovery(api_discovery_items: dict[str, Any]) -> None:
    """Apidiscovery mock response."""
    data = deepcopy(API_DISCOVERY_RESPONSE)
    if api_discovery_items:
        data["data"]["apiList"].append(api_discovery_items)
    respx.post(f"http://{DEFAULT_HOST}:80/axis-cgi/apidiscovery.cgi").respond(json=data)


@pytest.fixture(name="port_management_payload")
def fixture_io_port_management_data() -> dict[str, Any]:
    """Property parameter data."""
    return PORT_MANAGEMENT_RESPONSE


@pytest.fixture(name="param_properties_payload")
def fixture_param_properties_data() -> str:
    """Property parameter data."""
    return PROPERTIES_RESPONSE


@pytest.fixture(name="param_ports_payload")
def fixture_param_ports_data() -> str:
    """Property parameter data."""
    return PORTS_RESPONSE


@pytest.fixture(name="mqtt_status_code")
def fixture_mqtt_status_code() -> int:
    """Property parameter data."""
    return 200


@pytest.fixture(name="mock_default_requests")
def fixture_default_requests(mock_requests: Callable[[str], None]) -> None:
    """Mock default Vapix requests responses."""
    mock_requests(DEFAULT_HOST)


@pytest.fixture(name="config_entry_factory")
async def fixture_config_entry_factory(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_requests: Callable[[str], None],
) -> ConfigEntryFactoryType:
    """Fixture factory to set up Axis network device."""

    async def __mock_setup_config_entry() -> MockConfigEntry:
        config_entry.add_to_hass(hass)
        mock_requests(config_entry.data[CONF_HOST])
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        return config_entry

    return __mock_setup_config_entry


@pytest.fixture(name="config_entry_setup")
async def fixture_config_entry_setup(
    config_entry_factory: ConfigEntryFactoryType,
) -> MockConfigEntry:
    """Define a fixture to set up Axis network device."""
    return await config_entry_factory()


# RTSP fixtures


@pytest.fixture(autouse=True, name="_mock_rtsp_client")
def fixture_axis_rtsp_client() -> Generator[_RtspClientMock]:
    """No real RTSP communication allowed."""
    with patch("axis.stream_manager.RTSPClient") as rtsp_client_mock:
        rtsp_client_mock.return_value.session.state = State.STOPPED

        async def start_stream() -> None:
            """Set state to playing when calling RTSPClient.start."""
            rtsp_client_mock.return_value.session.state = State.PLAYING

        rtsp_client_mock.return_value.start = start_stream

        def stop_stream() -> None:
            """Set state to stopped when calling RTSPClient.stop."""
            rtsp_client_mock.return_value.session.state = State.STOPPED

        rtsp_client_mock.return_value.stop = stop_stream

        def make_rtsp_call(data: dict[str, Any] | None = None, state: str = "") -> None:
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


@pytest.fixture(autouse=True, name="mock_rtsp_event")
def fixture_rtsp_event(_mock_rtsp_client: _RtspClientMock) -> RtspEventMock:
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

        _mock_rtsp_client(data=event.encode("utf-8"))

    return send_event


@pytest.fixture(autouse=True, name="mock_rtsp_signal_state")
def fixture_rtsp_signal_state(_mock_rtsp_client: _RtspClientMock) -> RtspStateType:
    """Fixture to allow mocking RTSP state signalling."""

    def send_signal(connected: bool) -> None:
        """Signal state change of RTSP connection."""
        signal = Signal.PLAYING if connected else Signal.FAILED
        _mock_rtsp_client(state=signal)

    return send_signal
