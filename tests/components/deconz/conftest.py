"""deconz conftest."""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Generator
from types import MappingProxyType
from typing import Any, Protocol
from unittest.mock import patch

from pydeconz.websocket import Signal
import pytest

from homeassistant.components.deconz.const import DOMAIN as DECONZ_DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.light.conftest import mock_light_profiles  # noqa: F401
from tests.test_util.aiohttp import AiohttpClientMocker


class ConfigEntryFactoryType(Protocol):
    """Fixture factory that can set up deCONZ config entry."""

    async def __call__(self, entry: MockConfigEntry = ..., /) -> MockConfigEntry:
        """Set up a deCONZ config entry."""


type WebsocketDataType = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]
type WebsocketStateType = Callable[[str], Coroutine[Any, Any, None]]


class _WebsocketMock(Protocol):
    async def __call__(
        self, data: dict[str, Any] | None = None, state: str = ""
    ) -> None: ...


# Config entry fixtures

API_KEY = "1234567890ABCDEF"
BRIDGE_ID = "01234E56789A"
HOST = "1.2.3.4"
PORT = 80


@pytest.fixture(name="config_entry")
def fixture_config_entry(
    config_entry_data: MappingProxyType[str, Any],
    config_entry_options: MappingProxyType[str, Any],
    config_entry_source: str,
) -> MockConfigEntry:
    """Define a config entry fixture."""
    return MockConfigEntry(
        domain=DECONZ_DOMAIN,
        entry_id="1",
        unique_id=BRIDGE_ID,
        data=config_entry_data,
        options=config_entry_options,
        source=config_entry_source,
    )


@pytest.fixture(name="config_entry_data")
def fixture_config_entry_data() -> MappingProxyType[str, Any]:
    """Define a config entry data fixture."""
    return {
        CONF_API_KEY: API_KEY,
        CONF_HOST: HOST,
        CONF_PORT: PORT,
    }


@pytest.fixture(name="config_entry_options")
def fixture_config_entry_options() -> MappingProxyType[str, Any]:
    """Define a config entry options fixture."""
    return {}


@pytest.fixture(name="config_entry_source")
def fixture_config_entry_source() -> str:
    """Define a config entry source fixture."""
    return SOURCE_USER


# Request mocks


@pytest.fixture(name="mock_put_request")
def fixture_put_request(
    aioclient_mock: AiohttpClientMocker, config_entry_data: MappingProxyType[str, Any]
) -> Callable[[str, str], AiohttpClientMocker]:
    """Mock a deCONZ put request."""
    _host = config_entry_data[CONF_HOST]
    _port = config_entry_data[CONF_PORT]
    _api_key = config_entry_data[CONF_API_KEY]

    def __mock_requests(path: str, host: str = "") -> AiohttpClientMocker:
        url = f"http://{host or _host}:{_port}/api/{_api_key}{path}"
        aioclient_mock.put(url, json={}, headers={"content-type": CONTENT_TYPE_JSON})
        return aioclient_mock

    return __mock_requests


@pytest.fixture(name="mock_requests")
def fixture_get_request(
    aioclient_mock: AiohttpClientMocker,
    config_entry_data: MappingProxyType[str, Any],
    config_payload: dict[str, Any],
    alarm_system_payload: dict[str, Any],
    group_payload: dict[str, Any],
    light_payload: dict[str, Any],
    sensor_payload: dict[str, Any],
    deconz_payload: dict[str, Any],
) -> Callable[[str], None]:
    """Mock default deCONZ requests responses."""
    _host = config_entry_data[CONF_HOST]
    _port = config_entry_data[CONF_PORT]
    _api_key = config_entry_data[CONF_API_KEY]

    data = deconz_payload
    data.setdefault("alarmsystems", alarm_system_payload)
    data.setdefault("config", config_payload)
    data.setdefault("groups", group_payload)
    if "state" in light_payload:
        light_payload = {"0": light_payload}
    data.setdefault("lights", light_payload)
    if "state" in sensor_payload or "config" in sensor_payload:
        sensor_payload = {"0": sensor_payload}
    data.setdefault("sensors", sensor_payload)

    def __mock_requests(host: str = "") -> None:
        url = f"http://{host or _host}:{_port}/api/{_api_key}"
        aioclient_mock.get(
            url,
            json=deconz_payload | {"config": config_payload},
            headers={
                "content-type": CONTENT_TYPE_JSON,
            },
        )

    return __mock_requests


# Request payload fixtures


@pytest.fixture(name="deconz_payload")
def fixture_data() -> dict[str, Any]:
    """Combine multiple payloads with one fixture."""
    return {}


@pytest.fixture(name="alarm_system_payload")
def fixture_alarm_system_data() -> dict[str, Any]:
    """Alarm system data."""
    return {}


@pytest.fixture(name="config_payload")
def fixture_config_data() -> dict[str, Any]:
    """Config data."""
    return {
        "bridgeid": BRIDGE_ID,
        "ipaddress": HOST,
        "mac": "00:11:22:33:44:55",
        "modelid": "deCONZ",
        "name": "deCONZ mock gateway",
        "sw_version": "2.05.69",
        "uuid": "1234",
        "websocketport": 1234,
    }


@pytest.fixture(name="group_payload")
def fixture_group_data() -> dict[str, Any]:
    """Group data."""
    return {}


@pytest.fixture(name="light_payload")
def fixture_light_data() -> dict[str, Any]:
    """Light data.

    Should be
    - one light data payload {"state": ...}
    - multiple lights {"1": ..., "2": ...}
    """
    return {}


@pytest.fixture(name="sensor_payload")
def fixture_sensor_data() -> dict[str, Any]:
    """Sensor data.

    Should be
     - one sensor data payload {"config": ..., "state": ...} ("0")
     - multiple sensors {"1": ..., "2": ...}
    """
    return {}


@pytest.fixture(name="config_entry_factory")
async def fixture_config_entry_factory(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_requests: Callable[[str], None],
) -> ConfigEntryFactoryType:
    """Fixture factory that can set up deCONZ integration."""

    async def __mock_setup_config_entry(
        entry: MockConfigEntry = config_entry, /
    ) -> MockConfigEntry:
        entry.add_to_hass(hass)
        mock_requests(entry.data[CONF_HOST])
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry

    return __mock_setup_config_entry


@pytest.fixture(name="config_entry_setup")
async def fixture_config_entry_setup(
    config_entry_factory: ConfigEntryFactoryType,
) -> MockConfigEntry:
    """Fixture providing a set up instance of deCONZ integration."""
    return await config_entry_factory()


# Websocket fixtures


@pytest.fixture(autouse=True, name="_mock_websocket")
def fixture_websocket() -> Generator[_WebsocketMock]:
    """No real websocket allowed."""
    with patch("pydeconz.gateway.WSClient") as mock:

        async def make_websocket_call(
            data: dict[str, Any] | None = None, state: str = ""
        ) -> None:
            """Generate a websocket call."""
            pydeconz_gateway_session_handler = mock.call_args[0][3]

            signal: Signal
            if data:
                mock.return_value.data = data
                signal = Signal.DATA
            elif state:
                mock.return_value.state = state
                signal = Signal.CONNECTION_STATE
            await pydeconz_gateway_session_handler(signal)

        yield make_websocket_call


@pytest.fixture(name="mock_websocket_data")
def fixture_websocket_data(_mock_websocket: _WebsocketMock) -> WebsocketDataType:
    """Fixture to send websocket data."""

    async def change_websocket_data(data: dict[str, Any]) -> None:
        """Provide new data on the websocket."""
        if "t" not in data:
            data["t"] = "event"
        if "e" not in data:
            data["e"] = "changed"
        if "id" not in data:
            data["id"] = "0"
        await _mock_websocket(data=data)

    return change_websocket_data


@pytest.fixture(name="light_ws_data")
def fixture_light_websocket_data(
    mock_websocket_data: WebsocketDataType,
) -> WebsocketDataType:
    """Fixture to send light data over websocket."""

    async def send_light_data(data: dict[str, Any]) -> None:
        """Send light data on the websocket."""
        await mock_websocket_data({"r": "lights"} | data)

    return send_light_data


@pytest.fixture(name="sensor_ws_data")
def fixture_sensor_websocket_data(
    mock_websocket_data: WebsocketDataType,
) -> WebsocketDataType:
    """Fixture to send sensor data over websocket."""

    async def send_sensor_data(data: dict[str, Any]) -> None:
        """Send sensor data on the websocket."""
        await mock_websocket_data({"r": "sensors"} | data)

    return send_sensor_data


@pytest.fixture(name="mock_websocket_state")
def fixture_websocket_state(_mock_websocket: _WebsocketMock) -> WebsocketStateType:
    """Fixture to set websocket state."""

    async def change_websocket_state(state: str) -> None:
        """Simulate a change to the websocket connection state."""
        await _mock_websocket(state=state)

    return change_websocket_state
