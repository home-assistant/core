"""Test the qBittorrent config flow."""
from homeassistant.components.qbittorrent.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SOURCE,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

CONFIG_VALID = {
    CONF_URL: "http://localhost:8080",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
    CONF_VERIFY_SSL: True,
}

CONFIG_INVALID_AUTH = {
    CONF_URL: "http://localhost:8080",
    CONF_USERNAME: "null",
    CONF_PASSWORD: "none",
    CONF_VERIFY_SSL: True,
}

CONFIG_CANNOT_CONNECT = {
    CONF_URL: "http://nowhere:23456",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
    CONF_VERIFY_SSL: True,
}

CONFIG_IMPORT_VALID = {
    CONF_URL: "http://localhost:8080",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
}


async def test_show_form_no_input(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER


async def test_flow_user(hass: HomeAssistant, ok) -> None:
    """Test user initialized flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=CONFIG_VALID,
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == CONFIG_VALID


async def test_invalid_auth(hass: HomeAssistant, invalid_auth) -> None:
    """Test user initialized flow with invalid credential."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=CONFIG_INVALID_AUTH,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER
    assert result["errors"] == {"base": "invalid_auth"}


async def test_cannot_connect(hass: HomeAssistant, cannot_connect) -> None:
    """Test user initialized flow with connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=CONFIG_INVALID_AUTH,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_user_already_configured(hass: HomeAssistant) -> None:
    """Test user initialized flow with duplicate server."""
    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_VALID)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data=CONFIG_VALID
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_import(hass: HomeAssistant) -> None:
    """Test import step."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_IMPORT},
        data=CONFIG_IMPORT_VALID,
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == CONFIG_VALID


async def test_flow_import_already_configured(hass: HomeAssistant) -> None:
    """Test import step already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_VALID)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_IMPORT},
        data=CONFIG_IMPORT_VALID,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
