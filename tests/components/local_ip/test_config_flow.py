"""Tests for the local_ip config_flow."""
from __future__ import annotations

from homeassistant import data_entry_flow
from homeassistant.components.local_ip.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_config_flow(hass: HomeAssistant, mock_get_source_ip) -> None:
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()
    state = hass.states.get(f"sensor.{DOMAIN}")
    assert state


async def test_already_setup(hass: HomeAssistant, mock_get_source_ip) -> None:
    """Test we abort if already setup."""
    MockConfigEntry(
        domain=DOMAIN,
        data={},
    ).add_to_hass(hass)

    # Should fail, same NAME
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
