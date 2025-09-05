"""Test the configuration flow for MyNeoMitis integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aiohttp import ClientConnectionError, ClientError, ClientResponseError, RequestInfo
import pyaxencoapi
import pytest

from homeassistant import config_entries
from homeassistant.components.frontend import URL
from homeassistant.components.myneomitis.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
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
    with patch(pyaxencoapi.PyAxencoAPI) as mock_api:
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
            "token": "tok",
            "refresh_token": "rtok",
            "user_id": "user-123",
        }


@pytest.mark.asyncio
async def test_flow_raises_on_network_error(hass: HomeAssistant) -> None:
    """Test that a network error during login raises an exception."""
    with patch(pyaxencoapi.PyAxencoAPI) as mock_api:
        instance = mock_api.return_value
        instance.login = AsyncMock(side_effect=Exception("Network error"))

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        with pytest.raises(Exception, match="Network error"):
            await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
            )


@pytest.mark.asyncio
async def test_abort_if_already_configured(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test abort when entry already exists."""
    monkeypatch.setattr(
        hass.config_entries,
        "async_entries",
        lambda *args, **kwargs: [object()],
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"

    hass.config_entries.async_entries = lambda *args, **kwargs: []


def make_client_response_error(status: int) -> ClientResponseError:
    """Create a mock ClientResponseError with the given status code."""
    return ClientResponseError(
        request_info=RequestInfo(
            url=URL("https://api.fake"),
            method="POST",
            headers={},
            real_url=URL("https://api.fake"),
        ),
        history=[],
        status=status,
    )


@pytest.mark.asyncio
async def test_auth_failed(hass: HomeAssistant) -> None:
    """Test that an authentication error during login raises an exception."""
    with patch(pyaxencoapi.PyAxencoAPI) as mock_api:
        instance = mock_api.return_value
        instance.login = AsyncMock(side_effect=make_client_response_error(401))

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
        )

        assert result2["type"] == "form"
        assert result2["errors"]["base"] == "auth_failed"


@pytest.mark.asyncio
async def test_http_error(hass: HomeAssistant) -> None:
    """Test that an HTTP error during login raises an exception."""
    with patch(pyaxencoapi.PyAxencoAPI) as mock_api:
        instance = mock_api.return_value
        instance.login = AsyncMock(side_effect=make_client_response_error(500))

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
        )

        assert result2["type"] == "form"
        assert result2["errors"]["base"] == "connection_error"


@pytest.mark.asyncio
async def test_connection_error(hass: HomeAssistant) -> None:
    """Test that a connection error during login raises an exception."""
    with patch(pyaxencoapi.PyAxencoAPI) as mock_api:
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
        assert result2["errors"]["base"] == "connection_error"


@pytest.mark.asyncio
async def test_generic_client_error(hass: HomeAssistant) -> None:
    """Test that a generic client error during login raises an exception."""
    with patch(pyaxencoapi.PyAxencoAPI) as mock_api:
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
        assert result2["errors"]["base"] == "unknown_error"


@pytest.mark.asyncio
async def test_runtime_error(hass: HomeAssistant) -> None:
    """Test that a runtime error during login raises an exception."""
    with patch(pyaxencoapi.PyAxencoAPI) as mock_api:
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
        assert result2["errors"]["base"] == "unknown_error"
