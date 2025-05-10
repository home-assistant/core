"""Test config flow for Swing2Sleep Smarla integration."""

import pytest

from homeassistant.components.smarla.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_SERIAL_NUMBER, MOCK_USER_INPUT

from tests.common import MockConfigEntry


async def test_config_flow(hass: HomeAssistant, mock_refresh_token_success) -> None:
    """Test creating a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=MOCK_USER_INPUT
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_SERIAL_NUMBER
    assert result["data"] == MOCK_USER_INPUT
    assert result["result"].unique_id == MOCK_SERIAL_NUMBER


@pytest.mark.parametrize("error", ["malformed_token", "invalid_auth"])
async def test_form_error(
    hass: HomeAssistant, request: pytest.FixtureRequest, error: str
) -> None:
    """Test we show user form on invalid auth."""
    error_patch = request.getfixturevalue(f"{error}_patch")
    with error_patch:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    request.getfixturevalue("mock_refresh_token_success")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=MOCK_USER_INPUT
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_device_exists_abort(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_refresh_token_success
) -> None:
    """Test we abort config flow if Smarla device already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=MOCK_USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
