"""Test Free Mobile config flow."""

from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.components.free_mobile.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import CONF_INPUT, TEST_USERNAME


async def test_flow_user(hass: HomeAssistant, mock_freesms: AsyncMock) -> None:
    """Test user initialized flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )

    assert mock_freesms.send_sms.call_count == 1
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == f"Free Mobile ({TEST_USERNAME})"
    assert result.get("data") == {
        CONF_USERNAME: TEST_USERNAME,
        CONF_ACCESS_TOKEN: CONF_INPUT[CONF_ACCESS_TOKEN],
    }


async def test_flow_duplicate_username(
    hass: HomeAssistant, mock_freesms: AsyncMock
) -> None:
    """Test user initialized flow with duplicate username."""
    # Create first entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY

    # Try to create second entry with same username
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_flow_user_with_403_response(
    hass: HomeAssistant, mock_freesms: AsyncMock
) -> None:
    """Test user flow with 403 response - returns error for invalid credentials."""
    mock_freesms.send_sms.return_value.status_code = 403
    mock_freesms.send_sms.return_value.ok = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "authentication_failed"}


async def test_flow_import(hass: HomeAssistant, mock_freesms: AsyncMock) -> None:
    """Test import flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=CONF_INPUT,
    )

    assert mock_freesms.send_sms.call_count == 1
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == f"Free Mobile ({TEST_USERNAME})"
    assert result.get("data") == {
        CONF_USERNAME: TEST_USERNAME,
        CONF_ACCESS_TOKEN: CONF_INPUT[CONF_ACCESS_TOKEN],
    }


async def test_flow_import_duplicate(
    hass: HomeAssistant, mock_freesms: AsyncMock
) -> None:
    """Test import flow with duplicate entry."""
    # Create first entry via user flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY

    # Try to import with same username
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=CONF_INPUT,
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
