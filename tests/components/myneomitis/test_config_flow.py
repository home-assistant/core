"""Test the configuration flow for MyNeoMitis integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aiohttp import ClientConnectionError, ClientError, ClientResponseError, RequestInfo
import pytest

from homeassistant import config_entries
from homeassistant.components.frontend import URL
from homeassistant.components.myneomitis.const import (
    CONF_REFRESH_TOKEN,
    CONF_USER_ID,
    DOMAIN,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import event

TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "password123"


@pytest.fixture(autouse=True)
def disable_track_time_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None]:
    """Disable track_time_interval to avoid persistent timers."""
    monkeypatch.setattr(
        event, "track_time_interval", lambda hass, action, interval: None
    )
    return


@pytest.mark.asyncio
async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test successful user flow for MyNeoMitis integration."""
    with patch(
        "homeassistant.components.myneomitis.config_flow.PyAxencoAPI"
    ) as mock_api:
        instance = mock_api.return_value
        instance.login = AsyncMock()
        instance.user_id = "user-123"
        instance.token = "tok"
        instance.refresh_token = "rtok"

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
        )
        assert result2["type"] == "create_entry"
        assert result2["title"] == f"MyNeo ({TEST_EMAIL})"
        assert result2["data"] == {
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_TOKEN: "tok",
            CONF_REFRESH_TOKEN: "rtok",
            CONF_USER_ID: "user-123",
        }


@pytest.mark.asyncio
async def test_flow_raises_on_network_error(hass: HomeAssistant) -> None:
    """Test that a network error during login shows an error in the form."""
    with patch(
        "homeassistant.components.myneomitis.config_flow.PyAxencoAPI"
    ) as mock_api:
        instance = mock_api.return_value
        instance.login = AsyncMock(side_effect=ClientError("Network error"))

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
        )
        assert result2["type"] == "form"
        assert result2["errors"]["base"] == "unknown"


@pytest.mark.asyncio
async def test_abort_if_already_configured(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test abort when entry already exists."""
    # Create an existing config entry using hass.config_entries
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    with patch(
        "homeassistant.components.myneomitis.config_flow.PyAxencoAPI"
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.login = AsyncMock()
        mock_api.user_id = "test_user_id"
        mock_api.token = "test_token"
        mock_api.refresh_token = "test_refresh"

        # First entry - should succeed
        result1 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
        )
        assert result1["type"] == "create_entry"
        await hass.async_block_till_done()

        # Second entry with same user_id - should abort
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
        )
        assert result3["type"] == "abort"
        assert result3["reason"] == "already_configured"


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


@pytest.mark.asyncio
async def test_auth_failed(hass: HomeAssistant) -> None:
    """Test that an authentication error during login shows an error in the form."""
    with patch(
        "homeassistant.components.myneomitis.config_flow.PyAxencoAPI"
    ) as mock_api:
        instance = mock_api.return_value

        async def raise_auth(*args, **kwargs):
            raise make_client_response_error(401)

        instance.login = AsyncMock(side_effect=raise_auth)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
        )
        assert result2["type"] == "form"
        assert result2["errors"]["base"] == "invalid_auth"


@pytest.mark.asyncio
async def test_http_error(hass: HomeAssistant) -> None:
    """Test that an HTTP error during login shows an error in the form."""
    with patch(
        "homeassistant.components.myneomitis.config_flow.PyAxencoAPI"
    ) as mock_api:
        instance = mock_api.return_value

        async def raise_http(*args, **kwargs):
            raise make_client_response_error(500)

        instance.login = AsyncMock(side_effect=raise_http)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
        )
        assert result2["type"] == "form"
        assert result2["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_connection_error(hass: HomeAssistant) -> None:
    """Test that a connection error during login shows an error in the form."""
    with patch(
        "homeassistant.components.myneomitis.config_flow.PyAxencoAPI"
    ) as mock_api:
        instance = mock_api.return_value
        instance.login = AsyncMock(side_effect=ClientConnectionError())

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
        )
        assert result2["type"] == "form"
        assert result2["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_generic_client_error(hass: HomeAssistant) -> None:
    """Test that a generic client error during login shows an error in the form."""
    with patch(
        "homeassistant.components.myneomitis.config_flow.PyAxencoAPI"
    ) as mock_api:
        instance = mock_api.return_value
        instance.login = AsyncMock(side_effect=ClientError("oops"))

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
        )
        assert result2["type"] == "form"
        assert result2["errors"]["base"] == "unknown"


@pytest.mark.asyncio
async def test_runtime_error(hass: HomeAssistant) -> None:
    """Test that a runtime error during login shows an error in the form."""
    with patch(
        "homeassistant.components.myneomitis.config_flow.PyAxencoAPI"
    ) as mock_api:
        instance = mock_api.return_value
        instance.login = AsyncMock(side_effect=RuntimeError("boom"))

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
        )
        assert result2["type"] == "form"
        assert result2["errors"]["base"] == "unknown"
