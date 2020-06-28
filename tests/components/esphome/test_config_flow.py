"""Test config flow."""
from collections import namedtuple

import pytest

from homeassistant.components.esphome import DATA_KEY
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.async_mock import AsyncMock, MagicMock, patch
from tests.common import MockConfigEntry

MockDeviceInfo = namedtuple("DeviceInfo", ["uses_password", "name"])


@pytest.fixture
def mock_client():
    """Mock APIClient."""
    with patch("homeassistant.components.esphome.config_flow.APIClient") as mock_client:

        def mock_constructor(loop, host, port, password):
            """Fake the client constructor."""
            mock_client.host = host
            mock_client.port = port
            mock_client.password = password
            return mock_client

        mock_client.side_effect = mock_constructor
        mock_client.connect = AsyncMock()
        mock_client.disconnect = AsyncMock()

        yield mock_client


@pytest.fixture(autouse=True)
def mock_api_connection_error():
    """Mock out the try login method."""
    with patch(
        "homeassistant.components.esphome.config_flow.APIConnectionError",
        new_callable=lambda: OSError,
    ) as mock_error:
        yield mock_error


async def test_user_connection_works(hass, mock_client):
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        "esphome", context={"source": "user"}, data=None,
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    mock_client.device_info = AsyncMock(return_value=MockDeviceInfo(False, "test"))

    result = await hass.config_entries.flow.async_init(
        "esphome",
        context={"source": "user"},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 80},
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "127.0.0.1", CONF_PORT: 80, CONF_PASSWORD: ""}
    assert result["title"] == "test"

    assert len(mock_client.connect.mock_calls) == 1
    assert len(mock_client.device_info.mock_calls) == 1
    assert len(mock_client.disconnect.mock_calls) == 1
    assert mock_client.host == "127.0.0.1"
    assert mock_client.port == 80
    assert mock_client.password == ""


async def test_user_resolve_error(hass, mock_api_connection_error, mock_client):
    """Test user step with IP resolve error."""

    class MockResolveError(mock_api_connection_error):
        """Create an exception with a specific error message."""

        def __init__(self):
            """Initialize."""
            super().__init__("Error resolving IP address")

    with patch(
        "homeassistant.components.esphome.config_flow.APIConnectionError",
        new_callable=lambda: MockResolveError,
    ) as exc:
        mock_client.device_info.side_effect = exc
        result = await hass.config_entries.flow.async_init(
            "esphome",
            context={"source": "user"},
            data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "resolve_error"}

    assert len(mock_client.connect.mock_calls) == 1
    assert len(mock_client.device_info.mock_calls) == 1
    assert len(mock_client.disconnect.mock_calls) == 1


async def test_user_connection_error(hass, mock_api_connection_error, mock_client):
    """Test user step with connection error."""
    mock_client.device_info.side_effect = mock_api_connection_error

    result = await hass.config_entries.flow.async_init(
        "esphome",
        context={"source": "user"},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "connection_error"}

    assert len(mock_client.connect.mock_calls) == 1
    assert len(mock_client.device_info.mock_calls) == 1
    assert len(mock_client.disconnect.mock_calls) == 1


async def test_user_with_password(hass, mock_client):
    """Test user step with password."""
    mock_client.device_info = AsyncMock(return_value=MockDeviceInfo(True, "test"))

    result = await hass.config_entries.flow.async_init(
        "esphome",
        context={"source": "user"},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "authenticate"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "password1"}
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6053,
        CONF_PASSWORD: "password1",
    }
    assert mock_client.password == "password1"


async def test_user_invalid_password(hass, mock_api_connection_error, mock_client):
    """Test user step with invalid password."""
    mock_client.device_info = AsyncMock(return_value=MockDeviceInfo(True, "test"))

    result = await hass.config_entries.flow.async_init(
        "esphome",
        context={"source": "user"},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "authenticate"

    mock_client.connect.side_effect = mock_api_connection_error

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "invalid"}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "authenticate"
    assert result["errors"] == {"base": "invalid_password"}


async def test_discovery_initiation(hass, mock_client):
    """Test discovery importing works."""
    mock_client.device_info = AsyncMock(return_value=MockDeviceInfo(False, "test8266"))

    service_info = {
        "host": "192.168.43.183",
        "port": 6053,
        "hostname": "test8266.local.",
        "properties": {},
    }
    flow = await hass.config_entries.flow.async_init(
        "esphome", context={"source": "zeroconf"}, data=service_info
    )

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], user_input={}
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "test8266"
    assert result["data"][CONF_HOST] == "192.168.43.183"
    assert result["data"][CONF_PORT] == 6053

    assert result["result"]
    assert result["result"].unique_id == "test8266"


async def test_discovery_already_configured_hostname(hass, mock_client):
    """Test discovery aborts if already configured via hostname."""
    entry = MockConfigEntry(
        domain="esphome",
        data={CONF_HOST: "test8266.local", CONF_PORT: 6053, CONF_PASSWORD: ""},
    )

    entry.add_to_hass(hass)

    service_info = {
        "host": "192.168.43.183",
        "port": 6053,
        "hostname": "test8266.local.",
        "properties": {},
    }
    result = await hass.config_entries.flow.async_init(
        "esphome", context={"source": "zeroconf"}, data=service_info
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    assert entry.unique_id == "test8266"


async def test_discovery_already_configured_ip(hass, mock_client):
    """Test discovery aborts if already configured via static IP."""
    entry = MockConfigEntry(
        domain="esphome",
        data={CONF_HOST: "192.168.43.183", CONF_PORT: 6053, CONF_PASSWORD: ""},
    )

    entry.add_to_hass(hass)

    service_info = {
        "host": "192.168.43.183",
        "port": 6053,
        "hostname": "test8266.local.",
        "properties": {"address": "192.168.43.183"},
    }
    result = await hass.config_entries.flow.async_init(
        "esphome", context={"source": "zeroconf"}, data=service_info
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    assert entry.unique_id == "test8266"


async def test_discovery_already_configured_name(hass, mock_client):
    """Test discovery aborts if already configured via name."""
    entry = MockConfigEntry(
        domain="esphome",
        data={CONF_HOST: "192.168.43.183", CONF_PORT: 6053, CONF_PASSWORD: ""},
    )
    entry.add_to_hass(hass)

    mock_entry_data = MagicMock()
    mock_entry_data.device_info.name = "test8266"
    hass.data[DATA_KEY] = {entry.entry_id: mock_entry_data}

    service_info = {
        "host": "192.168.43.184",
        "port": 6053,
        "hostname": "test8266.local.",
        "properties": {"address": "test8266.local"},
    }
    result = await hass.config_entries.flow.async_init(
        "esphome", context={"source": "zeroconf"}, data=service_info
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    assert entry.unique_id == "test8266"
    assert entry.data[CONF_HOST] == "192.168.43.184"


async def test_discovery_duplicate_data(hass, mock_client):
    """Test discovery aborts if same mDNS packet arrives."""
    service_info = {
        "host": "192.168.43.183",
        "port": 6053,
        "hostname": "test8266.local.",
        "properties": {"address": "test8266.local"},
    }

    mock_client.device_info = AsyncMock(return_value=MockDeviceInfo(False, "test8266"))

    result = await hass.config_entries.flow.async_init(
        "esphome", data=service_info, context={"source": "zeroconf"}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_init(
        "esphome", data=service_info, context={"source": "zeroconf"}
    )
    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_in_progress"


async def test_discovery_updates_unique_id(hass, mock_client):
    """Test a duplicate discovery host aborts and updates existing entry."""
    entry = MockConfigEntry(
        domain="esphome",
        data={CONF_HOST: "192.168.43.183", CONF_PORT: 6053, CONF_PASSWORD: ""},
    )

    entry.add_to_hass(hass)

    service_info = {
        "host": "192.168.43.183",
        "port": 6053,
        "hostname": "test8266.local.",
        "properties": {"address": "test8266.local"},
    }
    result = await hass.config_entries.flow.async_init(
        "esphome", context={"source": "zeroconf"}, data=service_info
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    assert entry.unique_id == "test8266"
