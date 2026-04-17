"""Tests for Wibeee config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.components.wibeee.const import (
    CONF_UPDATE_MODE,
    DOMAIN,
    MODE_LOCAL_PUSH,
    MODE_POLLING,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_HOST


async def test_user_step_shows_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that the user step shows a form with host input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert CONF_HOST in result["data_schema"].schema


async def test_user_step_validates_and_goes_to_mode(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_wibeee_api_config_flow: AsyncMock,
) -> None:
    """Test user step validates device and moves to mode step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mode"


async def test_mode_step_creates_entry_polling(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_wibeee_api_config_flow: AsyncMock,
) -> None:
    """Test mode step creates entry with polling mode."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_UPDATE_MODE: MODE_POLLING},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == MOCK_HOST
    assert result["options"][CONF_UPDATE_MODE] == MODE_POLLING


async def test_mode_step_creates_entry_push(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_wibeee_api_config_flow: AsyncMock,
) -> None:
    """Test mode step creates entry with local push mode."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_UPDATE_MODE: MODE_LOCAL_PUSH},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == MOCK_HOST
    assert result["options"][CONF_UPDATE_MODE] == MODE_LOCAL_PUSH


async def test_options_flow(hass: HomeAssistant, loaded_entry) -> None:
    """Test options flow."""

    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_UPDATE_MODE: MODE_POLLING,
            "scan_interval": 60,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert loaded_entry.options[CONF_UPDATE_MODE] == MODE_POLLING
