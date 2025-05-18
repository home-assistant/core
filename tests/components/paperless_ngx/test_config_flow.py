"""Tests for the AdGuard Home config flow."""

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

from tests.common import MockConfigEntry


async def test_show_config_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


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
    mock_client,
    side_effect,
    expected_error,
) -> None:
    """Test user step shows correct error for various client initialization issues."""
    mock_client.initialize.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == expected_error


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
    assert config_entry.title == "Paperless-ngx"
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.data == USER_INPUT


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
