"""Tests the Decora WiFi config flow."""

from unittest.mock import patch

from homeassistant.components.decora_wifi.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER


async def test_form_no_input(hass):
    """Test that the form is presented."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == "form"

    user_data = {
        "username": "fakeaccount@email.abc",
        "password": "--fakepassword--",
    }

    with patch(
        "homeassistant.components.decora_wifi.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.decora_wifi.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.config_entries.ConfigFlow.async_set_unique_id"
    ) as mock_set_unique_id, patch(
        "homeassistant.config_entries.ConfigFlow._abort_if_unique_id_configured"
    ) as mock_abort_if_uid_configured:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_data,
        )
        await hass.async_block_till_done()

    # Verify basic info
    assert result2["title"] == "Leviton Decora WiFi"
    assert result2["data"] == user_data

    # Make sure entities are set up
    assert result2["type"] == "create_entry"
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1

    # Make sure the config flow will only run once
    assert len(mock_set_unique_id.mock_calls) == 1
    assert len(mock_abort_if_uid_configured.mock_calls) == 1


async def test_import(hass):
    """Test that the form is not presented."""

    user_data = {
        "username": "fakeaccount@email.abc",
        "password": "--fakepassword--",
    }

    with patch(
        "homeassistant.components.decora_wifi.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.decora_wifi.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.config_entries.ConfigFlow.async_set_unique_id"
    ) as mock_set_unique_id, patch(
        "homeassistant.config_entries.ConfigFlow._abort_if_unique_id_configured"
    ) as mock_abort_if_uid_configured:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=user_data
        )
        await hass.async_block_till_done()

    # Verify basic info
    assert result["title"] == "Leviton Decora WiFi"
    assert result["data"] == user_data

    # Make sure entities are set up
    assert result["type"] == "create_entry"
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1

    # Make sure the config flow will only run once
    assert len(mock_set_unique_id.mock_calls) == 1
    assert len(mock_abort_if_uid_configured.mock_calls) == 1
