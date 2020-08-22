"""Test the Risco config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.risco.config_flow import (
    CannotConnectError,
    UnauthorizedError,
)
from homeassistant.components.risco.const import DOMAIN

from tests.async_mock import AsyncMock, PropertyMock, patch

TEST_SITE_NAME = "test-site-name"
TEST_DATA = {
    "username": "test-username",
    "password": "test-password",
    "pin": "1234",
}


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.risco.config_flow.RiscoAPI.login", return_value=True,
    ), patch(
        "homeassistant.components.risco.config_flow.RiscoAPI.site_name",
        new_callable=PropertyMock(return_value=TEST_SITE_NAME),
    ), patch(
        "homeassistant.components.risco.config_flow.RiscoAPI.close", AsyncMock()
    ) as mock_close, patch(
        "homeassistant.components.risco.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.risco.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_DATA
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == TEST_SITE_NAME
    assert result2["data"] == TEST_DATA
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    mock_close.assert_awaited_once()


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.risco.config_flow.RiscoAPI.login",
        side_effect=UnauthorizedError,
    ), patch(
        "homeassistant.components.risco.config_flow.RiscoAPI.close", AsyncMock()
    ) as mock_close:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_DATA
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}
    mock_close.assert_awaited_once()


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.risco.config_flow.RiscoAPI.login",
        side_effect=CannotConnectError,
    ), patch(
        "homeassistant.components.risco.config_flow.RiscoAPI.close", AsyncMock()
    ) as mock_close:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_DATA
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
    mock_close.assert_awaited_once()


async def test_form_exception(hass):
    """Test we handle unknown exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.risco.config_flow.RiscoAPI.login",
        side_effect=Exception,
    ), patch(
        "homeassistant.components.risco.config_flow.RiscoAPI.close", AsyncMock()
    ) as mock_close:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_DATA
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}
    mock_close.assert_awaited_once()
