"""Tests for the bosch_alarm config flow."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.bosch_alarm.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form_user(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_panel: AsyncMock,
    model_name: str,
    serial_number: str,
    config_flow_data: dict[str, Any],
) -> None:
    """Test the config flow for bosch_alarm."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_PORT: 7700},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        config_flow_data,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Bosch {model_name}"
    assert (
        result["data"]
        == {
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 7700,
            CONF_MODEL: model_name,
        }
        | config_flow_data
    )
    assert result["result"].unique_id == serial_number
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (asyncio.TimeoutError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_panel: AsyncMock,
    config_flow_data: dict[str, Any],
    exception: Exception,
    message: str,
) -> None:
    """Test we handle exceptions correctly."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    mock_panel.connect.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_PORT: 7700},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": message}

    mock_panel.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_PORT: 7700},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        config_flow_data,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (PermissionError, "invalid_auth"),
        (asyncio.TimeoutError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_exceptions_user(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_panel: AsyncMock,
    config_flow_data: dict[str, Any],
    exception: Exception,
    message: str,
) -> None:
    """Test we handle exceptions correctly."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_PORT: 7700},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}
    mock_panel.connect.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], config_flow_data
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": message}

    mock_panel.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], config_flow_data
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize("model", ["solution_3000", "amax_3000"])
async def test_entry_already_configured_host(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_panel: AsyncMock,
    config_flow_data: dict[str, Any],
) -> None:
    """Test if configuring an entity twice results in an error."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "0.0.0.0"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], config_flow_data
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("model", ["b5512"])
async def test_entry_already_configured_serial(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_panel: AsyncMock,
    config_flow_data: dict[str, Any],
) -> None:
    """Test if configuring an entity twice results in an error."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "0.0.0.0"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], config_flow_data
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
