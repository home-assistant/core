"""Test the Duke Energy config flow."""

from unittest.mock import AsyncMock, Mock

from aiohttp import ClientError, ClientResponseError, RequestInfo
import pytest

from homeassistant import config_entries
from homeassistant.components.duke_energy.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.usefixtures("recorder_mock", "test_api")
async def test_user(hass: HomeAssistant) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    # test with all provided
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "test@example.com"

    data = result.get("data")
    assert data
    assert data[CONF_USERNAME] == "test-username"
    assert data[CONF_PASSWORD] == "test-password"
    assert data[CONF_EMAIL] == "test@example.com"


@pytest.mark.usefixtures("recorder_mock", "mock_config_entry", "test_api")
async def test_abort_if_already_setup(hass: HomeAssistant) -> None:
    """Test we abort if the email is already setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


@pytest.mark.usefixtures("recorder_mock")
async def test_asserts(hass: HomeAssistant, test_api: Mock) -> None:
    """Test the failure scenarios."""

    # test with authentication error
    request_info = RequestInfo("https://test.com", "GET", {})
    test_api.authenticate = AsyncMock(
        side_effect=ClientResponseError(request_info, (), status=404)
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "invalid_auth"}

    # test with response error
    test_api.authenticate = AsyncMock(
        side_effect=ClientResponseError(request_info, (), status=500)
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "could_not_connect"}

    # test with ConnectionTimeout
    test_api.authenticate = AsyncMock(side_effect=TimeoutError())
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "could_not_connect"}

    # test with HTTPError
    test_api.authenticate = AsyncMock(side_effect=ClientError())
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "could_not_connect"}

    # test with random exception
    test_api.authenticate = AsyncMock(side_effect=Exception())
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "unknown"}
