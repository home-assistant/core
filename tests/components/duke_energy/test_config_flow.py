"""Test the Duke Energy config flow."""

from unittest.mock import AsyncMock, Mock

from aiohttp import ClientError, ClientResponseError
import pytest

from homeassistant import config_entries
from homeassistant.components.duke_energy.const import DOMAIN
from homeassistant.components.recorder import Recorder
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_user(
    hass: HomeAssistant,
    recorder_mock: Recorder,
    mock_api: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    # test with all provided
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "test@example.com"

    data = result.get("data")
    assert data
    assert data[CONF_USERNAME] == "test-username"
    assert data[CONF_PASSWORD] == "test-password"
    assert data[CONF_EMAIL] == "test@example.com"


async def test_abort_if_already_setup(
    hass: HomeAssistant,
    recorder_mock: Recorder,
    mock_api: AsyncMock,
    mock_config_entry: AsyncMock,
) -> None:
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


async def test_abort_if_already_setup_alternate_username(
    hass: HomeAssistant,
    recorder_mock: Recorder,
    mock_api: AsyncMock,
    mock_config_entry: AsyncMock,
) -> None:
    """Test we abort if the email is already setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (ClientResponseError(None, None, status=404), "invalid_auth"),
        (ClientResponseError(None, None, status=500), "cannot_connect"),
        (TimeoutError(), "cannot_connect"),
        (ClientError(), "cannot_connect"),
        (Exception(), "unknown"),
    ],
)
async def test_api_errors(
    hass: HomeAssistant,
    recorder_mock: Recorder,
    mock_api: Mock,
    side_effect,
    expected_error,
) -> None:
    """Test the failure scenarios."""
    mock_api.authenticate.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": expected_error}

    mock_api.authenticate.side_effect = None

    # test with all provided
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
