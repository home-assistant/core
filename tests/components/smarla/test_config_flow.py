"""Test config flow for Swing2Sleep Smarla integration."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.smarla.config_flow import Connection
from homeassistant.components.smarla.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_ACCESS_TOKEN = "eyJyZWZyZXNoVG9rZW4iOiJ0ZXN0IiwidG9rZW4iOiJ0ZXN0IiwiZGF0ZUNyZWF0ZWQiOiIyMDI1LTAxLTAxVDIzOjU5OjU5Ljk5OTk5OVoiLCJhcHBJZGVudGlmaWVyIjoiSEEtaG9tZWFzc2lzdGFudHRlc3QiLCJzZXJpYWxOdW1iZXIiOiJBQkNELUFCQ0QiLCJhcHBWZXJzaW9uIjoidW5rbm93biIsImFwcEN1bHR1cmUiOiJkZSJ9"
MOCK_ACCESS_TOKEN_JSON = '{"refreshToken": "test", "token": "test", "dateCreated": "2025-01-01T23:59:59.999999Z", "appIdentifier": "HA-homeassistanttest", "serialNumber": "ABCD-ABCD", "appVersion": "unknown", "appCulture": "de"}'
MOCK_SERIAL = "ABCD-ABCD"


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is shown initially."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test creating a config entry."""
    with patch.object(Connection, "get_token", new=AsyncMock(return_value=True)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_SERIAL
    assert result["data"] == {CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN_JSON}


async def test_invalid_auth(hass: HomeAssistant) -> None:
    """Test we show user form on invalid auth."""
    with patch.object(Connection, "get_token", new=AsyncMock(return_value=None)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_invalid_token(hass: HomeAssistant) -> None:
    """Test we handle invalid/malformed tokens."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data={CONF_ACCESS_TOKEN: "invalid_token"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_token"}


async def test_device_exists_abort(hass: HomeAssistant) -> None:
    """Test we abort config flow if Smarla device already configured."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_SERIAL,
        source="user",
    )
    config_entry.add_to_hass(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data={CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
