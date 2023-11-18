"""Test the Time & Date config flow."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.time_date.const import CONF_DISPLAY_OPTIONS, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the forms."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"display_options": ["time"]},
    )
    await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 1
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_single_instance(hass: HomeAssistant) -> None:
    """Test we get the forms."""

    entry = MockConfigEntry(
        domain=DOMAIN, data={}, options={CONF_DISPLAY_OPTIONS: ["time", "date"]}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"display_options": ["time"]},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test a successful import of yaml."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_DISPLAY_OPTIONS: ["time", "date"]},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Time & Date"
    assert result["options"] == {"display_options": ["time", "date"]}


async def test_import_flow_already_exist(hass: HomeAssistant) -> None:
    """Test import of yaml already exist."""

    entry = MockConfigEntry(
        domain=DOMAIN, data={}, options={CONF_DISPLAY_OPTIONS: ["time", "date"]}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_DISPLAY_OPTIONS: ["time", "date"]},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_timezone_not_set(hass: HomeAssistant) -> None:
    """Test time zone not set."""
    hass.config.time_zone = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"display_options": ["time"]},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "timezone_not_exist"}


async def test_options(hass: HomeAssistant) -> None:
    """Test updating options."""
    entry = MockConfigEntry(domain=DOMAIN, data={"display_options": ["time"]})
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"display_options": ["time", "date"]},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {"display_options": ["time", "date"]}
