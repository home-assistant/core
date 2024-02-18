"""Tests for the SMTP config flow."""

from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
import homeassistant.components.notify as notify
from homeassistant.components.smtp.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from .const import (
    MOCKED_CONFIG_ENTRY_DATA,
    MOCKED_USER_ADVANCED_DATA,
    MOCKED_USER_BASIC_DATA,
)

from tests.common import MockConfigEntry


@patch(
    "homeassistant.components.smtp.notify.SMTPClient.connection_is_valid",
    lambda x: True,
)
async def test_import_entry(hass: HomeAssistant) -> None:
    """Test import of a confif entry from yaml."""
    assert await async_setup_component(
        hass,
        notify.DOMAIN,
        {
            notify.DOMAIN: [
                {
                    "name": DOMAIN,
                    "platform": DOMAIN,
                    "recipient": "test@example.com",
                    "sender": "test@example.com",
                },
            ]
        },
    )
    # Wait for discovery to finish
    await hass.async_block_till_done()
    assert hass.services.has_service(notify.DOMAIN, DOMAIN)


async def test_no_import(hass: HomeAssistant) -> None:
    """Test platform setup without config succeeds."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})


@pytest.mark.parametrize(
    ("user_input", "advanced_settings"),
    [(MOCKED_USER_BASIC_DATA, False), (MOCKED_USER_ADVANCED_DATA, True)],
)
async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    user_input: dict[str, Any],
    advanced_settings: bool,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_USER,
            "show_advanced_options": advanced_settings,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    def _connection_is_valid(errors: dict[str, str] | None = None) -> bool:
        """Check for valid config, verify connectivity."""
        return True

    with patch(
        "homeassistant.components.smtp.notify.SMTPClient.connection_is_valid",
        side_effect=_connection_is_valid,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "smtp"
    assert result2["data"] == MOCKED_CONFIG_ENTRY_DATA
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("mocked_user_input", "errors"),
    [
        (
            {"recipient": ["test@example.com", "not_a_valid_email"]},
            {"recipient": "invalid_email_address"},
        ),
        ({"sender": "not_a_valid_email"}, {"sender": "invalid_email_address"}),
        ({"username": "someuser"}, {"password": "username_and_password"}),
        ({"password": "somepassword"}, {"username": "username_and_password"}),
    ],
)
async def test_invalid_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mocked_user_input: dict[str, Any],
    errors: dict[str, str],
) -> None:
    """Test form validation works."""
    user_input = deepcopy(MOCKED_USER_BASIC_DATA)
    user_input.update(mocked_user_input)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == errors
    assert len(mock_setup_entry.mock_calls) == 0


async def test_entry_already_configured(hass: HomeAssistant) -> None:
    """Test aborting if the entry is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCKED_CONFIG_ENTRY_DATA)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCKED_USER_BASIC_DATA,
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


@pytest.mark.parametrize("error", ["authentication_failed", "connection_refused"])
async def test_form_invalid_auth_or_connection_refused(
    hass: HomeAssistant, error: str
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    def _connection_is_valid(errors: dict[str, str] | None = None) -> bool:
        """Check for valid config, verify connectivity."""
        errors["base"] = error
        return False

    with patch(
        "homeassistant.components.smtp.notify.SMTPClient.connection_is_valid",
        side_effect=_connection_is_valid,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCKED_USER_BASIC_DATA
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {
        "base": error,
    }
