"""Tests for honeywell config flow."""
import asyncio
from unittest.mock import MagicMock, patch

import aiosomecomfort
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.honeywell.const import (
    CONF_COOL_AWAY_TEMPERATURE,
    CONF_HEAT_AWAY_TEMPERATURE,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

FAKE_CONFIG = {
    "username": "fake",
    "password": "user",
    "away_cool_temperature": 88,
    "away_heat_temperature": 61,
}


async def test_show_authenticate_form(hass: HomeAssistant) -> None:
    """Test that the config form is shown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_connection_error(hass: HomeAssistant, client: MagicMock) -> None:
    """Test that an error message is shown on connection fail."""
    client.login.side_effect = aiosomecomfort.device.ConnectionError
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=FAKE_CONFIG
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_auth_error(hass: HomeAssistant, client: MagicMock) -> None:
    """Test that an error message is shown on login fail."""
    client.login.side_effect = aiosomecomfort.device.AuthError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=FAKE_CONFIG
    )
    assert result["errors"] == {"base": "invalid_auth"}


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test that the config entry is created."""
    with patch(
        "homeassistant.components.honeywell.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=FAKE_CONFIG
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == FAKE_CONFIG


async def test_show_option_form(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that the option form is shown."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.components.honeywell.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_create_option_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that the config entry is created."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.components.honeywell.async_setup_entry",
        return_value=True,
    ):
        options_form = await hass.config_entries.options.async_init(
            config_entry.entry_id
        )
        result = await hass.config_entries.options.async_configure(
            options_form["flow_id"],
            user_input={CONF_COOL_AWAY_TEMPERATURE: 1, CONF_HEAT_AWAY_TEMPERATURE: 2},
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        CONF_COOL_AWAY_TEMPERATURE: 1,
        CONF_HEAT_AWAY_TEMPERATURE: 2,
    }


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test a successful reauth flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
        unique_id="test-username",
    )
    mock_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.honeywell.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": SOURCE_REAUTH,
                "unique_id": mock_entry.unique_id,
                "entry_id": mock_entry.entry_id,
            },
            data={CONF_USERNAME: "test-username", CONF_PASSWORD: "new-password"},
        )

    await hass.async_block_till_done()

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.honeywell.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "new-username", CONF_PASSWORD: "new-password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert mock_entry.data == {
        CONF_USERNAME: "new-username",
        CONF_PASSWORD: "new-password",
    }


async def test_reauth_flow_auth_error(hass: HomeAssistant, client: MagicMock) -> None:
    """Test an authorization error reauth flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
        unique_id="test-username",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_entry.unique_id,
            "entry_id": mock_entry.entry_id,
        },
        data={CONF_USERNAME: "test-username", CONF_PASSWORD: "new-password"},
    )
    await hass.async_block_till_done()

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    client.login.side_effect = aiosomecomfort.device.AuthError
    with patch(
        "homeassistant.components.honeywell.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "new-username", CONF_PASSWORD: "new-password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


@pytest.mark.parametrize(
    "error",
    [
        aiosomecomfort.device.ConnectionError,
        aiosomecomfort.device.ConnectionTimeout,
        asyncio.TimeoutError,
    ],
)
async def test_reauth_flow_connnection_error(
    hass: HomeAssistant, client: MagicMock, error
) -> None:
    """Test a connection error reauth flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
        unique_id="test-username",
    )
    mock_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_entry.unique_id,
            "entry_id": mock_entry.entry_id,
        },
        data={CONF_USERNAME: "test-username", CONF_PASSWORD: "new-password"},
    )
    await hass.async_block_till_done()

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    client.login.side_effect = error

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "new-username", CONF_PASSWORD: "new-password"},
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
