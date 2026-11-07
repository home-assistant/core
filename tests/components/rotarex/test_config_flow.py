"""Test the Rotarex config flow."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from rotarex_dimes_srg_api import InvalidAuth, RotarexConnectionError

from homeassistant.components.rotarex.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

USER_INPUT = {CONF_EMAIL: "Test@Example.com", CONF_PASSWORD: "test_password"}


async def test_form(
    hass: HomeAssistant, mock_rotarex_api: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the full user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test@Example.com"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == "test@example.com"
    mock_rotarex_api.login.assert_awaited_once()
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (InvalidAuth, "invalid_auth"),
        (RotarexConnectionError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_rotarex_api: AsyncMock,
    exception: type[Exception],
    error: str,
) -> None:
    """Test we handle errors and can recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_rotarex_api.login.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_rotarex_api.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_rotarex_api")
async def test_form_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort when the account is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
