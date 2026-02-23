"""Test the configuration flow for MyNeomitis integration."""

from unittest.mock import AsyncMock

from aiohttp import ClientConnectionError, ClientError, ClientResponseError, RequestInfo
import pytest
from yarl import URL

from homeassistant.components.myneomitis.const import CONF_USER_ID, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
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


async def test_user_flow_success(
    hass: HomeAssistant,
    mock_pyaxenco_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test successful user flow for MyNeomitis integration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"MyNeomitis ({TEST_EMAIL})"
    assert result["data"] == {
        CONF_EMAIL: TEST_EMAIL,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_USER_ID: "user-123",
    }
    assert result["result"].unique_id == "user-123"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (ClientConnectionError(), "cannot_connect"),
        (make_client_response_error(401), "invalid_auth"),
        (make_client_response_error(403), "unknown"),
        (make_client_response_error(500), "cannot_connect"),
        (ClientError("Network error"), "unknown"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_flow_errors(
    hass: HomeAssistant,
    mock_pyaxenco_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test flow errors and recovery to CREATE_ENTRY."""
    mock_pyaxenco_client.login.side_effect = side_effect

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

    mock_pyaxenco_client.login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_abort_if_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Test abort when an entry for the same user_id already exists."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
