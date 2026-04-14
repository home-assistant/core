"""Test the Min/Max config flow."""

from homeassistant import config_entries
from homeassistant.components.min_max.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_config_flow_aborts(hass: HomeAssistant) -> None:
    """Test the config flow aborts."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "migrated_to_groups"
