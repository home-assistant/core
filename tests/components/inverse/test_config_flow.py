"""Test the Inverse config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.inverse.const import DOMAIN
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er


@pytest.mark.asyncio
async def test_config_flow_basic(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the config flow creates an entry wrapping a source entity."""
    # Start user flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result.get("errors") is None

    # Submit entity to wrap
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ENTITY_ID: "switch.ceiling"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    # Inverse stores selection in data, no options flow
    assert result["data"] == {CONF_ENTITY_ID: "switch.ceiling"}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {CONF_ENTITY_ID: "switch.ceiling"}
    assert config_entry.options == {}


@pytest.mark.asyncio
async def test_config_flow_registered_entity_hides_source(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the config flow hides a registered source entity and copies name."""
    switch_entity_entry = entity_registry.async_get_or_create(
        "switch", "test", "unique", suggested_object_id="ceiling"
    )
    assert switch_entity_entry.entity_id == "switch.ceiling"
    entity_registry.async_update_entity(
        "switch.ceiling", original_name="ABC", hidden_by=None
    )

    # Start user flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result.get("errors") is None

    # Submit selection
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ENTITY_ID: "switch.ceiling"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ENTITY_ID: "switch.ceiling"}
    assert len(mock_setup_entry.mock_calls) == 1

    # Source entity should be hidden by integration
    updated = entity_registry.async_get("switch.ceiling")
    assert updated is not None
    assert updated.hidden_by == er.RegistryEntryHider.INTEGRATION
