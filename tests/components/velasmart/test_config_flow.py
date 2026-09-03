"""Tests for the VelaSmart config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from velasmart import VelaSmartApiAuthError, VelaSmartApiClient, VelaSmartApiError

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


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (VelaSmartApiAuthError("invalid credentials"), "invalid_auth"),
        (VelaSmartApiError("network error"), "cannot_connect"),
    ],
)
async def test_validation_error(
    hass: HomeAssistant,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test that validation errors are surfaced on the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    with patch.object(
        VelaSmartApiClient,
        "authenticate",
        new_callable=AsyncMock,
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "wrong"},
        )
    assert result["type"] == "form"
    assert result["errors"] == {"base": expected_error}


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


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test that a duplicate account aborts the flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "correct"},
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_reauth_flow_shows_form(hass: HomeAssistant) -> None:
    """Test that reauthentication shows the confirm form."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": entry.entry_id},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"


async def test_reauth_invalid_auth(hass: HomeAssistant) -> None:
    """Test that reauthentication surfaces invalid credentials."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": entry.entry_id},
    )
    with patch.object(
        VelaSmartApiClient,
        "authenticate",
        new_callable=AsyncMock,
        side_effect=VelaSmartApiAuthError("invalid credentials"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "wrong"},
        )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reauth_successful(hass: HomeAssistant) -> None:
    """Test that reauthentication updates the entry and aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "old"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": entry.entry_id},
    )
    with patch.object(
        VelaSmartApiClient,
        "authenticate",
        new_callable=AsyncMock,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "new"},
        )
    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
