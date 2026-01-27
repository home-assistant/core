"""Test the configuration flow for MyNeoMitis integration."""

from unittest.mock import AsyncMock

from aiohttp import ClientConnectionError, ClientError, ClientResponseError, RequestInfo
import pytest

from homeassistant.components.frontend import URL
from homeassistant.components.myneomitis.const import (
    CONF_REFRESH_TOKEN,
    CONF_USER_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "password123"


def make_client_response_error(status: int) -> ClientResponseError:
    """Create a mock ClientResponseError with the given status code."""
    request_info = RequestInfo(
        url=URL("https://api.fake"),
        method="POST",
        headers={},
        real_url=URL("https://api.fake"),
    )
    return ClientResponseError(
        request_info=request_info,
        history=(),
        status=status,
        message="error",
        headers=None,
    )


async def test_user_flow_success(hass: HomeAssistant, mock_pyaxenco_client) -> None:
    """Test successful user flow for MyNeoMitis integration."""
    instance = mock_pyaxenco_client
    instance.login = AsyncMock()
    instance.user_id = "user-123"
    instance.token = "tok"
    instance.refresh_token = "rtok"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"MyNeo ({TEST_EMAIL})"
    assert result["data"] == {
        CONF_EMAIL: TEST_EMAIL,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_TOKEN: "tok",
        CONF_REFRESH_TOKEN: "rtok",
        CONF_USER_ID: "user-123",
    }
    assert result["result"].unique_id == instance.user_id


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (ClientConnectionError(), "cannot_connect"),
        (make_client_response_error(401), "invalid_auth"),
        (ClientError("Network error"), "unknown"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_flow_errors(
    hass: HomeAssistant, mock_pyaxenco_client, side_effect, expected_error
) -> None:
    """Test flow errors and recovery to CREATE_ENTRY."""
    instance = mock_pyaxenco_client
    instance.login = AsyncMock(side_effect=side_effect)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == expected_error

    instance.login = AsyncMock()
    instance.user_id = "user-123"
    instance.token = "tok"
    instance.refresh_token = "rtok"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_abort_if_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_pyaxenco_client
) -> None:
    """Test abort when an entry for the same user_id already exists."""
    mock_config_entry.add_to_hass(hass)

    mock_api = mock_pyaxenco_client
    mock_api.login = AsyncMock()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_auth_failed(hass: HomeAssistant, mock_pyaxenco_client) -> None:
    """Test that an authentication error during login shows an error in the form."""
    instance = mock_pyaxenco_client

    async def raise_auth(*args, **kwargs):
        raise make_client_response_error(401)

    instance.login = AsyncMock(side_effect=raise_auth)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_http_error(hass: HomeAssistant, mock_pyaxenco_client) -> None:
    """Test that an HTTP error during login shows an error in the form."""
    instance = mock_pyaxenco_client

    async def raise_http(*args, **kwargs):
        raise make_client_response_error(500)

    instance.login = AsyncMock(side_effect=raise_http)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_connection_error(hass: HomeAssistant, mock_pyaxenco_client) -> None:
    """Test that a connection error during login shows an error in the form."""
    instance = mock_pyaxenco_client
    instance.login = AsyncMock(side_effect=ClientConnectionError())

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_generic_client_error(hass: HomeAssistant, mock_pyaxenco_client) -> None:
    """Test that a generic client error during login shows an error in the form."""
    instance = mock_pyaxenco_client
    instance.login = AsyncMock(side_effect=ClientError("oops"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"


async def test_runtime_error(hass: HomeAssistant, mock_pyaxenco_client) -> None:
    """Test that a runtime error during login shows an error in the form."""
    instance = mock_pyaxenco_client
    instance.login = AsyncMock(side_effect=RuntimeError("boom"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"
