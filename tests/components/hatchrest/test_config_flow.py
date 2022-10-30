"""Tests for the hatchrest config flow."""


from homeassistant import config_entries
from homeassistant.components.hatchrest.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import VALID_HATCHREST, VALID_HATCHREST_ENTRY


async def test_async_step_bluetooth_valid(hass: HomeAssistant):
    """Test setup of valid bluetooth device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VALID_HATCHREST,
    )
    await hass.async_block_till_done()

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("data", {}).get("address") == VALID_HATCHREST.address


async def test_async_step_bluetooth_duplicate(hass: HomeAssistant):
    """Test setup of duplicate bluetooth device."""
    entry = VALID_HATCHREST_ENTRY
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VALID_HATCHREST,
    )
    await hass.async_block_till_done()

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
