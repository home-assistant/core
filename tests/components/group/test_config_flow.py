"""Test the Group config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.group.config_flow import SUPPORTED_DOMAINS
from homeassistant.components.group.const import DOMAIN
from homeassistant.const import CONF_DOMAIN, CONF_ENTITIES, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM
from homeassistant.loader import async_get_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize("domain", SUPPORTED_DOMAINS)
async def test_form(hass: HomeAssistant, domain: str) -> None:
    """Test we can create a new group from the UI."""

    hass.states.async_set(f"{domain}.dummy", STATE_ON)
    hass.states.async_set(f"{domain}.dummy2", STATE_ON)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DOMAIN: domain,
        },
    )
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.group.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_ENTITIES: [f"{domain}.dummy", f"{domain}.dummy2"],
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
    integration = await async_get_integration(hass, domain)
    assert result3["title"] == f"{integration.name} Group"
    assert result3["data"] == {CONF_DOMAIN: domain}
    assert result3["options"] == {
        CONF_ENTITIES: [f"{domain}.dummy", f"{domain}.dummy2"],
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("domain", SUPPORTED_DOMAINS)
async def test_options(hass: HomeAssistant, domain: str) -> None:
    """Test we can edit an existing group from the UI."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DOMAIN: domain},
        options={CONF_ENTITIES: [f"{domain}.dummy", f"{domain}.dummy2"]},
    )
    entry.add_to_hass(hass)

    hass.states.async_set(f"{domain}.dummy", STATE_ON)
    hass.states.async_set(f"{domain}.dummy2", STATE_ON)
    hass.states.async_set(f"{domain}.dummy3", STATE_ON)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.group.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_ENTITIES: [
                    f"{domain}.dummy",
                    f"{domain}.dummy2",
                    f"{domain}.dummy3",
                ],
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert entry.options == {
        CONF_ENTITIES: [f"{domain}.dummy", f"{domain}.dummy2", f"{domain}.dummy3"]
    }
    assert len(mock_setup_entry.mock_calls) == 1
