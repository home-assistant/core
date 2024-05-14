"""Test the Binary sensor as X config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.binary_sensor_as_x.const import CONF_TARGET_DOMAIN, DOMAIN
from homeassistant.const import CONF_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from . import PLATFORMS_TO_TEST


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_config_flow(
    hass: HomeAssistant,
    target_domain: Platform,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ENTITY_ID: "binary_sensor.basement",
            CONF_TARGET_DOMAIN: target_domain,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "basement"
    assert result["data"] == {}
    assert result["options"] == {
        CONF_ENTITY_ID: "binary_sensor.basement",
        CONF_TARGET_DOMAIN: target_domain,
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        CONF_ENTITY_ID: "binary_sensor.basement",
        CONF_TARGET_DOMAIN: target_domain,
    }


@pytest.mark.parametrize(
    ("hidden_by_before", "hidden_by_after"),
    [
        (er.RegistryEntryHider.USER, er.RegistryEntryHider.USER),
        (None, er.RegistryEntryHider.INTEGRATION),
    ],
)
@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_config_flow_registered_entity(
    hass: HomeAssistant,
    target_domain: Platform,
    mock_setup_entry: AsyncMock,
    hidden_by_before: er.RegistryEntryHider | None,
    hidden_by_after: er.RegistryEntryHider,
) -> None:
    """Test the config flow hides a registered entity."""
    registry = er.async_get(hass)
    binary_sensor_entity_entry = registry.async_get_or_create(
        "binary_sensor", "test", "unique", suggested_object_id="basement"
    )
    assert binary_sensor_entity_entry.entity_id == "binary_sensor.basement"
    registry.async_update_entity("binary_sensor.basement", hidden_by=hidden_by_before)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ENTITY_ID: "binary_sensor.basement",
            CONF_TARGET_DOMAIN: target_domain,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "basement"
    assert result["data"] == {}
    assert result["options"] == {
        CONF_ENTITY_ID: "binary_sensor.basement",
        CONF_TARGET_DOMAIN: target_domain,
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        CONF_ENTITY_ID: "binary_sensor.basement",
        CONF_TARGET_DOMAIN: target_domain,
    }

    binary_sensor_entity_entry = registry.async_get("binary_sensor.basement")
    assert binary_sensor_entity_entry.hidden_by == hidden_by_after
