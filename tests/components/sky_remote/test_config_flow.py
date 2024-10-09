"""Test the Sky Remote config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from skyboxremote import LEGACY_PORT

from homeassistant import config_entries
from homeassistant.components.sky_remote.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_user_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, sample_config, mock_remote_control
) -> None:
    """Test we can setup an entry."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: sample_config[CONF_HOST]},
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["version"] == 1
    assert result["data"] == sample_config

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("mock_remote_control", [LEGACY_PORT], indirect=True)
async def test_user_flow_legacy_device(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    sample_config,
    mock_remote_control,
) -> None:
    """Test we can setup an entry with a legacy port."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: sample_config[CONF_HOST]},
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["version"] == 1
    assert result["data"] == {**sample_config, CONF_PORT: LEGACY_PORT}

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("mock_remote_control", [6], indirect=True)
async def test_user_flow_unconnectable(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    sample_config,
    mock_remote_control,
) -> None:
    """Test we can setup an entry."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: sample_config[CONF_HOST]},
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    assert len(mock_setup_entry.mock_calls) == 0
