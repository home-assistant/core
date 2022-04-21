"""Test the moonrker API connector."""
from __future__ import annotations

import asyncio
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from aiohttp import ClientConnectionError
from moonraker_api import ClientNotAuthenticatedError
from moonraker_api.const import (
    WEBSOCKET_STATE_CONNECTED,
    WEBSOCKET_STATE_CONNECTING,
    WEBSOCKET_STATE_STOPPED,
)
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.moonraker.connector import APIConnector, generate_signal
from homeassistant.components.moonraker.const import (
    DATA_CONNECTOR,
    SIGNAL_STATE_AVAILABLE,
    SIGNAL_UPDATE_MODULE,
)
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN

from tests.common import MockConfigEntry

HOST_NAME_1 = "test_host_1"
HOST_NAME_2 = "test_host_2"


def fake_api_call_method(method: str, **kwargs: Any) -> Any:
    """Return data for generic API calls."""
    if method == "printer.objects.query":
        return {
            "status": {
                "extruder": {
                    "temperature": 0.0,
                    "target": 0.0,
                    "power": 0.0,
                }
            }
        }
    return {"res_data": "success"}


@pytest.fixture
def moonraker_client() -> Generator:
    """Mock Moonraker API client."""
    with patch(
        "homeassistant.components.moonraker.connector.MoonrakerClient"
    ) as client_mock:

        def mock_constructor(
            listener, host, port, api_key, ssl, loop=None, timeout=0, session=None
        ):
            """Fake the client constructor."""
            client_mock.listener = listener
            client_mock.host = host
            client_mock.port = port
            client_mock.api_key = api_key
            client_mock.ssl = ssl
            client_mock.loop = loop
            client_mock.session = session
            client_mock.timeout = timeout
            return client_mock

        client_mock.side_effect = mock_constructor
        client_mock.connect = AsyncMock(return_value=True)
        client_mock.disconnect = AsyncMock(return_value=True)
        client_mock.get_klipper_status = AsyncMock(return_value="disconnected")
        client_mock.get_supported_modules = AsyncMock(
            return_value=["extruder", "heater_bed", "virtual_sdcard", "print_stats"]
        )
        client_mock.call_method = AsyncMock(side_effect=fake_api_call_method)
        yield client_mock


@pytest.fixture
def moonraker_listener() -> Generator:
    """Mock Moonraker API event listener."""
    with patch(
        "homeassistant.components.moonraker.connector.MoonrakerListener", autospec=True
    ) as listener_mock:
        yield listener_mock


def get_mock_entry(hass: HomeAssistant, entry_name: str) -> MockConfigEntry:
    """Generate a mock config entry for testing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=entry_name,
        title=entry_name,
        data={
            CONF_HOST: f"{entry_name}.local",
            CONF_PORT: 7125,
            CONF_SSL: False,
            CONF_API_KEY: "",
        },
    )
    entry.add_to_hass(hass)
    return entry


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Complete setup for entry."""
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def setup_and_connect(
    hass: HomeAssistant, moonraker_client: Mock
) -> APIConnector:
    """Create a mock entry, setup and connect to API."""
    entry = get_mock_entry(hass, HOST_NAME_1)
    await setup_entry(hass, entry)
    moonraker_client.start()

    return hass.data[DOMAIN][entry.entry_id][DATA_CONNECTOR]


async def test_generated_signals_are_unique(
    hass: HomeAssistant, mock_connector: Mock
) -> None:
    """Test that generated updates signas are unique per entry."""
    entry_1 = get_mock_entry(hass, HOST_NAME_1)
    entry_2 = get_mock_entry(hass, HOST_NAME_2)

    signal_1 = generate_signal(SIGNAL_STATE_AVAILABLE, entry_1.entry_id)
    signal_2 = generate_signal(SIGNAL_STATE_AVAILABLE, entry_2.entry_id)

    assert signal_1 != signal_2


async def test_start_stop_service_success(
    hass: HomeAssistant, moonraker_client: Mock
) -> None:
    """Test starting the moonraker api client."""
    entry = get_mock_entry(hass, HOST_NAME_1)
    await setup_entry(hass, entry)

    assert hass.data[DOMAIN][entry.entry_id]
    assert moonraker_client.call_count == 1
    assert moonraker_client.connect.call_count == 1

    connector = hass.data[DOMAIN][entry.entry_id][DATA_CONNECTOR]
    assert connector is not None
    assert connector.running is True

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert moonraker_client.disconnect.call_count == 1


async def test_start_service_authentication_error(
    hass: HomeAssistant, moonraker_client: Mock
) -> None:
    """Test starting the moonraker API client with an auth error."""
    moonraker_client.connect.side_effect = ClientNotAuthenticatedError

    with patch(
        "homeassistant.components.moonraker.config_flow.ConfigFlow.async_step_reauth",
        return_value={"type": data_entry_flow.RESULT_TYPE_FORM},
    ) as mock_reauth:
        entry = get_mock_entry(hass, HOST_NAME_1)
        try:
            await setup_entry(hass, entry)
        except ClientNotAuthenticatedError:
            pytest.fail("ClientNotAuthenticatedError should not be unhandled.")

        assert mock_reauth.call_count == 1


async def test_start_service_connection_error(
    hass: HomeAssistant, aiohttp_server: Mock, moonraker_client: Mock
) -> None:
    """Test starting the moonraker client with a connection error."""
    moonraker_client.connect.side_effect = ClientConnectionError
    entry = get_mock_entry(hass, HOST_NAME_1)
    try:
        await setup_entry(hass, entry)
    except ClientConnectionError:
        pytest.fail("ClientConnectionError should not be unhandled.")


async def test_start_service_timeout_error(
    hass: HomeAssistant, aiohttp_server: Mock, moonraker_client: Mock
) -> None:
    """Test starting the moonraker client with a connection error."""
    moonraker_client.connect.side_effect = asyncio.TimeoutError
    entry = get_mock_entry(hass, HOST_NAME_1)
    try:
        await setup_entry(hass, entry)
    except asyncio.TimeoutError:
        pytest.fail("asyncio.TimeoutError should not be unhandled.")


async def test_websocket_connecting_handler(
    hass: HomeAssistant, moonraker_client: Mock
) -> None:
    """Test handling of connecting event."""
    connector = await setup_and_connect(hass, moonraker_client)
    assert connector.retry_count == 0
    await connector.state_changed(WEBSOCKET_STATE_CONNECTING)
    assert connector.retry_count == 1
    await connector.state_changed(WEBSOCKET_STATE_CONNECTED)
    assert connector.retry_count == 0
    assert moonraker_client.get_klipper_status.call_count == 1


async def test_websocket_connected_ready_handler(
    hass: HomeAssistant, moonraker_client: Mock
) -> None:
    """Test API instance ready on connection."""
    moonraker_client.get_klipper_status.return_value = "ready"

    entry = get_mock_entry(hass, HOST_NAME_1)
    await setup_entry(hass, entry)
    moonraker_client.start()
    connector = hass.data[DOMAIN][entry.entry_id][DATA_CONNECTOR]

    update_signal = MagicMock()
    update_signal_name = generate_signal(
        SIGNAL_UPDATE_MODULE % "extruder", entry.entry_id
    )
    async_dispatcher_connect(hass, update_signal_name, update_signal)
    status_signal = MagicMock()
    status_signal_name = generate_signal(SIGNAL_STATE_AVAILABLE, entry.entry_id)
    async_dispatcher_connect(hass, status_signal_name, status_signal)
    await connector.state_changed(WEBSOCKET_STATE_CONNECTED)
    await hass.async_block_till_done()

    assert moonraker_client.get_klipper_status.call_count == 1
    assert moonraker_client.get_supported_modules.call_count == 1
    assert update_signal.call_args.args == (
        {"temperature": 0.0, "target": 0.0, "power": 0.0},
    )
    assert status_signal.call_args.args == (True,)


@patch("homeassistant.components.moonraker.connector.BACKOFF_TIME_LOWER_LIMIT", 0)
async def test_websocket_disconnected_handler(
    hass: HomeAssistant, moonraker_client: Mock
) -> None:
    """Test API instance disconnected handler."""
    entry = get_mock_entry(hass, HOST_NAME_1)
    await setup_entry(hass, entry)
    moonraker_client.start()
    connector = hass.data[DOMAIN][entry.entry_id][DATA_CONNECTOR]

    status_signal = MagicMock()
    status_signal_name = generate_signal(SIGNAL_STATE_AVAILABLE, entry.entry_id)
    async_dispatcher_connect(hass, status_signal_name, status_signal)
    await connector.state_changed(WEBSOCKET_STATE_STOPPED)
    await hass.async_block_till_done()

    assert status_signal.call_args.args == (False,)
    assert moonraker_client.connect.call_count == 2


async def test_exception_not_authorized_handler(
    hass: HomeAssistant, moonraker_client: Mock
) -> None:
    """Test a ClientNotAuthenticatedError raised by the API."""
    connector = await setup_and_connect(hass, moonraker_client)
    with patch(
        "homeassistant.components.moonraker.config_flow.ConfigFlow.async_step_reauth",
        return_value={"type": data_entry_flow.RESULT_TYPE_FORM},
    ) as mock_reauth:
        try:
            await connector.on_exception(ClientNotAuthenticatedError())
        except ClientNotAuthenticatedError:
            pytest.fail("ClientNotAuthenticated error should not be unhandled.")
        await hass.async_block_till_done()
        assert mock_reauth.call_count == 1


async def test_update_notification_handler(
    hass: HomeAssistant, moonraker_client: Mock
) -> None:
    """Test handling of update notifications from the API."""
    entry = get_mock_entry(hass, HOST_NAME_1)
    await setup_entry(hass, entry)
    moonraker_client.start()

    update_signal = MagicMock()
    update_signal_name = generate_signal(
        SIGNAL_UPDATE_MODULE % "extruder", entry.entry_id
    )
    async_dispatcher_connect(hass, update_signal_name, update_signal)

    update_data = (
        {
            "extruder": {
                "temperature": 0.0,
                "target": 0.0,
                "power": 0.0,
            }
        },
        0,
    )

    # First call to update with this timestamp will trigger an update
    connector = hass.data[DOMAIN][entry.entry_id][DATA_CONNECTOR]
    await connector.on_notification("notify_status_update", update_data)
    await hass.async_block_till_done()

    assert update_signal.call_args.args == (update_data[0]["extruder"],)

    # Second call with same timestamp will not dispatch
    await connector.on_notification("notify_status_update", update_data)
    await hass.async_block_till_done()

    assert update_signal.call_count == 1

    # Third call 1 second later will dispatch again
    update_data = (update_data[0], 1)
    await connector.on_notification("notify_status_update", update_data)
    await hass.async_block_till_done()

    assert update_signal.call_count == 2


@pytest.mark.parametrize(
    "notification,status",
    [
        ("notify_klippy_ready", True),
        ("notify_klippy_disconnected", False),
        ("notify_klippy_shutdown", False),
    ],
)
async def test_notify_klipper_ready_handler(
    hass: HomeAssistant, moonraker_client: Mock, notification: str, status: bool
) -> None:
    """Test handling of klipper ready message."""
    moonraker_client.get_klipper_status.return_value = "ready"

    entry = get_mock_entry(hass, HOST_NAME_1)
    await setup_entry(hass, entry)
    moonraker_client.start()
    connector = hass.data[DOMAIN][entry.entry_id][DATA_CONNECTOR]

    status_signal = MagicMock()
    status_signal_name = generate_signal(SIGNAL_STATE_AVAILABLE, entry.entry_id)
    async_dispatcher_connect(hass, status_signal_name, status_signal)
    await connector.on_notification(notification, None)
    await hass.async_block_till_done()

    assert status_signal.call_count == 1
    assert status_signal.call_args.args == (status,)
