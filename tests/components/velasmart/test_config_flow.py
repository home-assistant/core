"""Tests for the VelaSmart config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from velasmart import VelaSmartApiClient, VelaSmartApiError

from homeassistant.components.velasmart.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_user_step_shows_form(hass: HomeAssistant) -> None:
    """Test that the user step shows the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_invalid_auth(hass: HomeAssistant) -> None:
    """Test that invalid credentials show an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    with patch.object(
        VelaSmartApiClient,
        "authenticate",
        new_callable=AsyncMock,
        side_effect=VelaSmartApiError("invalid credentials"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "wrong"},
        )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_successful_config(hass: HomeAssistant) -> None:
    """Test that valid credentials create the entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    with patch.object(
        VelaSmartApiClient,
        "authenticate",
        new_callable=AsyncMock,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "correct"},
        )
    assert result["type"] == "create_entry"
    assert result["title"] == "VelaSmart"
    assert result["data"] == {
        CONF_USERNAME: "test@example.com",
        CONF_PASSWORD: "correct",
    }


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test that reauthentication can be triggered."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": entry.entry_id},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"
