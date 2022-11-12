"""Test cases for combined energy config flow."""
from unittest.mock import patch

import combined_energy.exceptions
import pytest

from homeassistant import config_entries
from homeassistant.components.combined_energy.const import CONF_INSTALLATION_ID, DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant


async def test_form(hass: HomeAssistant):
    """Test that a form is created."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "combined_energy.client.CombinedEnergy.installation", return_value=True
    ), patch(
        "homeassistant.components.combined_energy.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "user@example.com",
                CONF_PASSWORD: "AbCDeF",
                CONF_INSTALLATION_ID: 99999999,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Combined Energy"
    assert result2["data"] == {
        CONF_USERNAME: "user@example.com",
        CONF_PASSWORD: "AbCDeF",
        CONF_INSTALLATION_ID: 99999999,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "exception, expected_errors",
    (
        (combined_energy.exceptions.CombinedEnergyAuthError, {"base": "invalid_auth"}),
        (
            combined_energy.exceptions.CombinedEnergyPermissionError,
            {CONF_INSTALLATION_ID: "installation_not_accessible"},
        ),
        (
            combined_energy.exceptions.CombinedEnergyTimeoutError,
            {"base": "cannot_connect"},
        ),
    ),
)
async def test_form__where_api_returns_an_expected_error(
    hass: HomeAssistant, exception, expected_errors
):
    """Test behaviour of specific API errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "combined_energy.client.CombinedEnergy.installation", side_effect=exception
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "user@example.com",
                CONF_PASSWORD: "AbCDeF",
                CONF_INSTALLATION_ID: 99999999,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == expected_errors


async def test_form__where_api_returns_an_unexpected_error(hass: HomeAssistant, caplog):
    """Test behaviour of unexpected API errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "combined_energy.client.CombinedEnergy.installation",
        side_effect=combined_energy.exceptions.CombinedEnergyError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "user@example.com",
                CONF_PASSWORD: "AbCDeF",
                CONF_INSTALLATION_ID: 99999999,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
    assert "Unexpected error verifying connection to API" in caplog.text


async def test_form__where_installation_id_already_configured(hass: HomeAssistant):
    """Test behaviour when an installation id has already been configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["errors"] == {}

    # Add config entry
    await hass.config_entries.async_add(
        ConfigEntry(
            1,
            "combined_energy",
            "Combined Energy",
            {
                CONF_USERNAME: "user@example.com",
                CONF_PASSWORD: "AbCDeF",
                CONF_INSTALLATION_ID: 99999999,
            },
            source=config_entries.SOURCE_USER,
        )
    )

    with patch(
        "combined_energy.client.CombinedEnergy.installation",
        side_effect=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "user@example.com",
                CONF_PASSWORD: "AbCDeF",
                CONF_INSTALLATION_ID: 99999999,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {CONF_INSTALLATION_ID: "already_configured"}
