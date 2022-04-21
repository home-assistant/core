"""Test the moonraker config flow."""
import asyncio
from typing import Any, Generator
from unittest.mock import AsyncMock, Mock, patch

from moonraker_api.websockets.websocketclient import ClientNotAuthenticatedError
import pytest

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.moonraker.config_flow import CannotConnect
from homeassistant.components.moonraker.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.moonraker.async_setup_entry", return_value=True
    ):
        yield


def fake_api_call_method(method: str, **kwargs: Any) -> Any:
    """Return data for generic API calls."""
    if method == "printer.info":
        return {"hostname": "test-host"}
    elif method == "machine.system_info":
        return {"system_info": {"cpu_info": {"serial_number": "abcd1234"}}}
    return {"res_data": "success"}


@pytest.fixture
def moonraker_client() -> Generator:
    """Mock Moonraker API client."""
    with patch(
        "homeassistant.components.moonraker.config_flow.MoonrakerClient"
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
        client_mock.call_method = AsyncMock(side_effect=fake_api_call_method)
        yield client_mock


def get_mock_service_info() -> zeroconf.ZeroconfServiceInfo:
    """Get a mock service info object."""
    return zeroconf.ZeroconfServiceInfo(
        host="192.168.43.183",
        addresses=["192.168.43.183"],
        port=7120,
        hostname="test-host.local.",
        type="_moonraker._tcp.local.",
        name="Moonraker Instance",
        properties={},
    )


async def test_user_connection_works(
    hass: HomeAssistant, moonraker_client: Mock, mock_zeroconf: Mock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_SSL: False,
            CONF_API_KEY: None,
        },
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 80,
        CONF_API_KEY: None,
        CONF_SSL: False,
    }
    assert result["title"] == "test-host"


@pytest.mark.parametrize("exception", [CannotConnect, asyncio.TimeoutError])
async def test_user_resolve_connection_error(
    hass: HomeAssistant,
    moonraker_client: Mock,
    mock_zeroconf: Mock,
    exception: BaseException,
) -> None:
    """Test we handle invalid auth."""
    moonraker_client.connect.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_SSL: False,
            CONF_API_KEY: None,
        },
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_resolve_connection_fails_error(
    hass: HomeAssistant, moonraker_client: Mock, mock_zeroconf: Mock
) -> None:
    """Test we handle invalid auth."""
    moonraker_client.connect.return_value = False
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_SSL: False,
            CONF_API_KEY: None,
        },
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_resolve_authentication_error(
    hass: HomeAssistant, moonraker_client: Mock, mock_zeroconf: Mock
) -> None:
    """Test we handle invalid auth."""
    moonraker_client.connect.side_effect = ClientNotAuthenticatedError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_SSL: False,
            CONF_API_KEY: None,
        },
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_api_key"}


async def test_user_resolve_unknown_error(
    hass: HomeAssistant, moonraker_client: Mock, mock_zeroconf: Mock
) -> None:
    """Test we handle invalid auth."""
    moonraker_client.connect.side_effect = Exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_SSL: False,
            CONF_API_KEY: None,
        },
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


async def test_user_older_clients_succeed(
    hass: HomeAssistant, moonraker_client: Mock, mock_zeroconf: Mock
) -> None:
    """Test we handle older clients without a serial number."""

    def _fake_api_call_method(method: str, **kwargs: Any) -> Any:
        """Override the fake call_method responses."""
        if method == "machine.system_info":
            return {"system_info": {"cpu_info": {}}}
        else:
            return fake_api_call_method(method, **kwargs)

    moonraker_client.call_method.side_effect = _fake_api_call_method
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_SSL: False,
            CONF_API_KEY: None,
        },
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 80,
        CONF_API_KEY: None,
        CONF_SSL: False,
    }
    assert result["title"] == "test-host"


async def test_discovery_initiation(
    hass: HomeAssistant, moonraker_client: Mock, mock_zeroconf: Mock
) -> None:
    """Test discovery importing works."""
    service_info = get_mock_service_info()
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=service_info
    )

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], user_input={}
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "test-host"
    assert result["data"][CONF_HOST] == "test-host.local"
    assert result["data"][CONF_PORT] == 7120

    assert result["result"]


async def test_user_already_configured_hostname(
    hass: HomeAssistant, moonraker_client: Mock
) -> None:
    """Test discovery aborts if already configured via hostname."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "test-host.local",
            CONF_PORT: 7120,
            CONF_SSL: False,
            CONF_API_KEY: "",
        },
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: "test-host.local",
            CONF_PORT: 7120,
            CONF_SSL: False,
            CONF_API_KEY: "",
        },
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_discovery_already_configured_hostname(
    hass: HomeAssistant, moonraker_client: Mock
) -> None:
    """Test discovery aborts if already configured via hostname."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "test-host.local",
            CONF_PORT: 7120,
            CONF_SSL: False,
            CONF_API_KEY: "",
        },
    )

    entry.add_to_hass(hass)

    service_info = get_mock_service_info()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=service_info
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_discovery_already_configured_ip(
    hass: HomeAssistant, moonraker_client: Mock
) -> None:
    """Test discovery aborts if already configured via static IP."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.43.183",
            CONF_PORT: 7120,
            CONF_SSL: False,
            CONF_API_KEY: "",
        },
    )

    entry.add_to_hass(hass)

    service_info = get_mock_service_info()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=service_info
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_discovery_duplicate_data(
    hass: HomeAssistant, moonraker_client: Mock
) -> None:
    """Test discovery aborts if same mDNS packet arrives."""
    service_info = get_mock_service_info()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, data=service_info, context={"source": config_entries.SOURCE_ZEROCONF}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, data=service_info, context={"source": config_entries.SOURCE_ZEROCONF}
    )
    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_in_progress"


async def test_reauth_initiation(
    hass: HomeAssistant, moonraker_client: Mock, mock_zeroconf: Mock
) -> None:
    """Test reauth initiation shows form."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 7120,
            CONF_SSL: False,
            CONF_API_KEY: "",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 7120,
            CONF_SSL: False,
            CONF_API_KEY: "",
        },
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "reauth_successful"
