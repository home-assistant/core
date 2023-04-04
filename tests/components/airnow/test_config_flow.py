"""Test the AirNow config flow."""
from unittest.mock import AsyncMock

from pyairnow.errors import AirNowError, InvalidKeyError
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.airnow.const import DOMAIN
from homeassistant.core import HomeAssistant


async def test_form(hass: HomeAssistant, config, setup_airnow) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], config)
    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["data"] == config


@pytest.mark.parametrize("mock_api_get", [AsyncMock(side_effect=InvalidKeyError)])
async def test_form_invalid_auth(hass: HomeAssistant, config, setup_airnow) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], config)
    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


@pytest.mark.parametrize("data", [{}])
async def test_form_invalid_location(hass: HomeAssistant, config, setup_airnow) -> None:
    """Test we handle invalid location."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], config)
    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_location"}


@pytest.mark.parametrize("mock_api_get", [AsyncMock(side_effect=AirNowError)])
async def test_form_cannot_connect(hass: HomeAssistant, config, setup_airnow) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], config)
    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize("mock_api_get", [AsyncMock(side_effect=RuntimeError)])
async def test_form_unexpected(hass: HomeAssistant, config, setup_airnow) -> None:
    """Test we handle an unexpected error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], config)
    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_entry_already_exists(hass: HomeAssistant, config, config_entry) -> None:
    """Test that the form aborts if the Lat/Lng is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], config)
    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"
