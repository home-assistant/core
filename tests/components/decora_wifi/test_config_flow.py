"""Test the decora_wifi config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.decora_wifi.config_flow import CannotConnect
from homeassistant.components.decora_wifi.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]
    with patch(
        "homeassistant.components.decora_wifi.config_flow.DecoraWiFiSession.login",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test-username"
    assert result2["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }


@pytest.mark.parametrize(
    ("mock_login_kwargs", "expected_error"),
    (
        ({"return_value": False}, "invalid_auth"),
        ({"side_effect": CannotConnect}, "cannot_connect"),
    ),
)
async def test_form_errors(
    mock_login_kwargs, expected_error, hass: HomeAssistant
) -> None:
    """Test form errors based on api response."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Mock With Error
    with patch(
        "homeassistant.components.decora_wifi.config_flow.DecoraWiFiSession.login",
        **mock_login_kwargs,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "bad-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": expected_error}

    # Mock Success and ensure recovery
    with patch(
        "homeassistant.components.decora_wifi.config_flow.DecoraWiFiSession.login",
        return_value=True,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "bad-password",
            },
        )
    await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert "errors" not in result3


async def test_duplicate_error(hass: HomeAssistant) -> None:
    """Test that it disallows creating w/ same "username."""
    CONFIG = {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    entry = MockConfigEntry(domain=DOMAIN, unique_id="test-username", data=CONFIG)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.decora_wifi.config_flow.DecoraWiFiSession.login",
        return_value=True,
    ):
        await entry.async_setup(hass)
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=CONFIG
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_async_step_import_success(hass: HomeAssistant) -> None:
    """Test import step success."""

    with patch(
        "homeassistant.components.decora_wifi.config_flow.DecoraWiFiSession.login",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_USERNAME: "test-email", CONF_PASSWORD: "test-password"},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-email"
    assert result["data"] == {
        CONF_USERNAME: "test-email",
        CONF_PASSWORD: "test-password",
    }
