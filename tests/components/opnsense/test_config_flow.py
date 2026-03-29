"""Tests for the OPNsense config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from aioopnsense import OPNsenseApiError, OPNsenseAuthError

from homeassistant import config_entries
from homeassistant.components.opnsense.const import (
    CONF_API_SECRET,
    CONF_TRACKER_INTERFACES,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_USER_INPUT = {
    CONF_URL: "https://opnsense.local/api",
    CONF_API_KEY: "test_key",
    CONF_API_SECRET: "test_secret",
    CONF_VERIFY_SSL: False,
    CONF_TRACKER_INTERFACES: "",
}


def _mock_client(get_arp_result: list | None = None) -> AsyncMock:
    """Create a mock OPNsenseClient."""
    client = AsyncMock()
    client.get_arp = AsyncMock(return_value=get_arp_result or [])
    return client


async def test_user_form(hass: HomeAssistant) -> None:
    """Test we get the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_user_form_success(hass: HomeAssistant) -> None:
    """Test successful user config flow."""
    with (
        patch(
            "homeassistant.components.opnsense.config_flow.OPNsenseClient",
            return_value=_mock_client(),
        ),
        patch(
            "homeassistant.components.opnsense.OPNsenseClient",
            return_value=_mock_client(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "https://opnsense.local/api"
    assert result["data"][CONF_URL] == "https://opnsense.local/api"
    assert result["data"][CONF_API_KEY] == "test_key"
    assert result["data"][CONF_API_SECRET] == "test_secret"


async def test_user_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    mock_client = _mock_client()
    mock_client.get_arp = AsyncMock(side_effect=OPNsenseAuthError("auth failed"))

    with patch(
        "homeassistant.components.opnsense.config_flow.OPNsenseClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle connection error."""
    mock_client = _mock_client()
    mock_client.get_arp = AsyncMock(side_effect=OPNsenseApiError("connection failed"))

    with patch(
        "homeassistant.components.opnsense.config_flow.OPNsenseClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_form_already_configured(hass: HomeAssistant) -> None:
    """Test we abort if already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: "https://opnsense.local/api",
            CONF_API_KEY: "test_key",
            CONF_API_SECRET: "test_secret",
            CONF_VERIFY_SSL: False,
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.opnsense.config_flow.OPNsenseClient",
        return_value=_mock_client(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow(hass: HomeAssistant) -> None:
    """Test YAML import creates a config entry."""
    mock_client = _mock_client()
    mock_client.get_interfaces = AsyncMock(return_value={"igb0": "WAN", "igb1": "LAN"})

    with patch(
        "homeassistant.components.opnsense.OPNsenseClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_URL: "https://opnsense.local/api",
                CONF_API_KEY: "test_key",
                CONF_API_SECRET: "test_secret",
                CONF_VERIFY_SSL: False,
                CONF_TRACKER_INTERFACES: ["LAN", "WAN"],
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TRACKER_INTERFACES] == "LAN,WAN"
