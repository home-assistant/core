"""Test the Compit config flow."""

from unittest.mock import AsyncMock, Mock, patch

from compit_inext_api import Gate, SystemInfo
import pytest

from homeassistant import config_entries
from homeassistant.components.compit.config_flow import (
    CannotConnect,
    CompitConfigFlow,
    InvalidAuth,
)
from homeassistant.components.compit.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_async_step_user_success(hass: HomeAssistant) -> None:
    """Test user step with successful authentication."""
    flow = CompitConfigFlow()
    flow.hass = hass

    with (
        patch(
            "homeassistant.components.compit.config_flow.CompitAPI.authenticate",
            return_value=SystemInfo(
                gates=[Gate(label="Test", code="1", devices=[], id=1)]
            ),
        ),
        patch.object(flow, "async_set_unique_id", return_value=None),
        patch.object(flow, "_abort_if_unique_id_configured", return_value=None),
    ):
        result = await flow.async_step_user(
            {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Compit"
    assert result["data"] == {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"}


async def test_async_step_user_invalid_auth(hass: HomeAssistant) -> None:
    """Test user step with invalid authentication."""
    flow = CompitConfigFlow()
    flow.hass = hass

    with patch(
        "homeassistant.components.compit.config_flow.CompitAPI.authenticate",
        side_effect=InvalidAuth,
    ):
        result = await flow.async_step_user(
            {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_async_step_user_cannot_connect(hass: HomeAssistant) -> None:
    """Test user step with connection error."""
    flow = CompitConfigFlow()
    flow.hass = hass

    with patch(
        "homeassistant.components.compit.config_flow.CompitAPI.authenticate",
        side_effect=CannotConnect,
    ):
        result = await flow.async_step_user(
            {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_async_step_user_unknown_error(hass: HomeAssistant) -> None:
    """Test user step with unknown error."""
    flow = CompitConfigFlow()
    flow.hass = hass

    with patch(
        "homeassistant.components.compit.config_flow.CompitAPI.authenticate",
        side_effect=Exception,
    ):
        result = await flow.async_step_user(
            {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


@pytest.fixture
def mock_reauth_entry():
    """Return a mock config entry."""
    return config_entries.ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Compit",
        data={CONF_EMAIL: "test@example.com"},
        source=config_entries.SOURCE_REAUTH,
        entry_id="1",
        unique_id="compit_test@example.com",
        discovery_keys=None,
        minor_version=0,
        options={},
    )


async def test_async_step_reauth_confirm_success(hass: HomeAssistant) -> None:
    """Test reauth confirm step with successful authentication."""
    entry = mock_reauth_entry()
    hass.config_entries._entries[entry.entry_id] = entry

    flow = CompitConfigFlow()
    flow.hass = hass
    flow._get_reauth_entry = Mock(return_value=entry)

    with patch(
        "homeassistant.components.compit.config_flow.CompitAPI.authenticate",
        return_value=AsyncMock(
            return_value=SystemInfo(
                gates=[Gate(label="Test", code="1", devices=[], id=1)]
            )
        ),
    ):
        result = await flow.async_step_reauth_confirm(
            {CONF_PASSWORD: "new_password", CONF_EMAIL: "test@example.com"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_async_step_reauth_confirm_invalid_auth(hass: HomeAssistant) -> None:
    """Test reauth confirm step with invalid authentication."""
    flow = CompitConfigFlow()
    flow.hass = hass
    flow._get_reauth_entry = Mock(return_value=mock_reauth_entry())

    with patch(
        "homeassistant.components.compit.config_flow.CompitAPI.authenticate",
        side_effect=InvalidAuth,
    ):
        result = await flow.async_step_reauth_confirm({CONF_PASSWORD: "new_password"})

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_async_step_reauth_confirm_cannot_connect(hass: HomeAssistant) -> None:
    """Test reauth confirm step with connection error."""
    flow = CompitConfigFlow()
    flow.hass = hass
    flow._get_reauth_entry = Mock(return_value=mock_reauth_entry())

    with patch(
        "homeassistant.components.compit.config_flow.CompitAPI.authenticate",
        side_effect=CannotConnect,
    ):
        result = await flow.async_step_reauth_confirm({CONF_PASSWORD: "new_password"})

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_async_step_reauth_confirm_unknown_error(hass: HomeAssistant) -> None:
    """Test reauth confirm step with unknown error."""
    flow = CompitConfigFlow()
    flow.hass = hass
    flow._get_reauth_entry = Mock(return_value=mock_reauth_entry())

    with patch(
        "homeassistant.components.compit.config_flow.CompitAPI.authenticate",
        side_effect=Exception,
    ):
        result = await flow.async_step_reauth_confirm({CONF_PASSWORD: "new_password"})

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
