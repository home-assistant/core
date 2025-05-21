"""Tests for the Paperless-ngx config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock

from pypaperless.exceptions import (
    InitializationError,
    PaperlessConnectionError,
    PaperlessForbiddenError,
    PaperlessInactiveOrDeletedError,
    PaperlessInvalidTokenError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.paperless_ngx.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import USER_INPUT

from tests.common import MockConfigEntry, patch


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.paperless_ngx.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


async def test_full_config_flow(hass: HomeAssistant) -> None:
    """Test registering an integration and finishing flow works."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result
    assert result["flow_id"]
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    config_entry = result["result"]
    assert config_entry.title == USER_INPUT[CONF_HOST]
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.data == USER_INPUT
    assert config_entry.data[CONF_HOST] == USER_INPUT[CONF_HOST]
    assert config_entry.data[CONF_API_KEY] == USER_INPUT[CONF_API_KEY]


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (PaperlessConnectionError(), {CONF_HOST: "cannot_connect"}),
        (PaperlessInvalidTokenError(), {CONF_API_KEY: "invalid_api_key"}),
        (PaperlessInactiveOrDeletedError(), {CONF_API_KEY: "user_inactive_or_deleted"}),
        (PaperlessForbiddenError(), {CONF_API_KEY: "forbidden"}),
        (InitializationError(), {CONF_HOST: "cannot_connect"}),
        (Exception("BOOM!"), {"base": "unknown"}),
    ],
)
async def test_config_flow_error_handling(
    hass: HomeAssistant,
    mock_paperless: AsyncMock,
    side_effect: Exception,
    expected_error: dict[str, str],
) -> None:
    """Test user step shows correct error for various client initialization issues."""
    mock_paperless.initialize.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == expected_error

    mock_paperless.initialize.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == USER_INPUT[CONF_HOST]
    assert result["data"] == USER_INPUT
    assert result["data"][CONF_HOST] == USER_INPUT[CONF_HOST]
    assert result["data"][CONF_API_KEY] == USER_INPUT[CONF_API_KEY]


async def test_config_already_exists(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""
    MockConfigEntry(
        domain=DOMAIN,
        data=USER_INPUT,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=USER_INPUT,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
