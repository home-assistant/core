"""Test the Switch as X config flow."""
from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.switch_as_x.const import CONF_TARGET_DOMAIN, DOMAIN
from homeassistant.const import CONF_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM


@pytest.mark.parametrize("target_domain", (Platform.LIGHT,))
async def test_config_flow(
    hass: HomeAssistant,
    target_domain: Platform,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ENTITY_ID: "switch.ceiling",
            CONF_TARGET_DOMAIN: target_domain,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
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


@pytest.mark.parametrize("target_domain", (Platform.LIGHT,))
async def test_options(
    hass: HomeAssistant,
    target_domain: Platform,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfiguring."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ENTITY_ID: "switch.ceiling",
            CONF_TARGET_DOMAIN: target_domain,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry

    # Switch light has no options flow
    with pytest.raises(data_entry_flow.UnknownHandler):
        await hass.config_entries.options.async_init(config_entry.entry_id)
