"""Test the Switch as X config flow."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.switch_as_x.const import CONF_TARGET_DOMAIN, DOMAIN
from homeassistant.const import CONF_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

PLATFORMS_TO_TEST = (
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.SIREN,
)


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
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ENTITY_ID: "switch.ceiling",
            CONF_TARGET_DOMAIN: target_domain,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "ceiling"
    assert result["data"] == {}
    assert result["options"] == {
        CONF_ENTITY_ID: "switch.ceiling",
        CONF_TARGET_DOMAIN: target_domain,
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        CONF_ENTITY_ID: "switch.ceiling",
        CONF_TARGET_DOMAIN: target_domain,
    }


@pytest.mark.parametrize(
    ("hidden_by_before", "hidden_by_after"),
    (
        (er.RegistryEntryHider.USER, er.RegistryEntryHider.USER),
        (None, er.RegistryEntryHider.INTEGRATION),
    ),
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
    switch_entity_entry = registry.async_get_or_create(
        "switch", "test", "unique", suggested_object_id="ceiling"
    )
    assert switch_entity_entry.entity_id == "switch.ceiling"
    registry.async_update_entity("switch.ceiling", hidden_by=hidden_by_before)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ENTITY_ID: "switch.ceiling",
            CONF_TARGET_DOMAIN: target_domain,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "ceiling"
    assert result["data"] == {}
    assert result["options"] == {
        CONF_ENTITY_ID: "switch.ceiling",
        CONF_TARGET_DOMAIN: target_domain,
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        CONF_ENTITY_ID: "switch.ceiling",
        CONF_TARGET_DOMAIN: target_domain,
    }

    switch_entity_entry = registry.async_get("switch.ceiling")
    assert switch_entity_entry.hidden_by == hidden_by_after


@pytest.mark.parametrize("target_domain", PLATFORMS_TO_TEST)
async def test_options(
    hass: HomeAssistant,
    target_domain: Platform,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfiguring."""
    switch_as_x_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: "switch.ceiling",
            CONF_TARGET_DOMAIN: target_domain,
        },
        title="ABC",
    )
    switch_as_x_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(switch_as_x_config_entry.entry_id)
    await hass.async_block_till_done()

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry

    # Switch light has no options flow
    with pytest.raises(data_entry_flow.UnknownHandler):
        await hass.config_entries.options.async_init(config_entry.entry_id)
