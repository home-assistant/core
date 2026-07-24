"""Test the rtl_433 config flow."""

from __future__ import annotations

from unittest.mock import MagicMock

from pyrtl_433 import CannotConnect

from homeassistant.components.rtl_433.const import (
    CONF_HOST,
    CONF_PATH,
    CONF_PORT,
    CONF_SECURE,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_HOST, MOCK_PATH, MOCK_PORT, MOCK_UNIQUE_ID

from tests.common import MockConfigEntry


async def test_user_flow(
    hass: HomeAssistant,
    mock_rtl433_client: MagicMock,
) -> None:
    """Test the happy-path user flow creates a hub entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_PATH: MOCK_PATH,
            CONF_SECURE: False,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"rtl_433 ({MOCK_HOST})"
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_PORT: MOCK_PORT,
        CONF_PATH: MOCK_PATH,
        CONF_SECURE: False,
    }
    assert result["result"].unique_id == MOCK_UNIQUE_ID


async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    mock_rtl433_client: MagicMock,
) -> None:
    """Test the user flow shows ``cannot_connect`` then recovers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    mock_rtl433_client.validate_connection.side_effect = CannotConnect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_PATH: MOCK_PATH,
            CONF_SECURE: False,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # The server becomes reachable and the user retries successfully.
    mock_rtl433_client.validate_connection.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_PATH: MOCK_PATH,
            CONF_SECURE: False,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MOCK_UNIQUE_ID


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rtl433_client: MagicMock,
) -> None:
    """Test a second entry for the same host:port aborts as already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_PATH: MOCK_PATH,
            CONF_SECURE: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
