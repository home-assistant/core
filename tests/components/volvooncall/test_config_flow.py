"""Test the Volvo On Call config flow."""

from homeassistant import config_entries
from homeassistant.components.volvooncall.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Volvo On Call will be removed ❌"
    assert result["data"] == {}


async def test_flow_works_multiple_times(hass: HomeAssistant) -> None:
    """Test the config flow can be completed multiple times."""
    # First flow
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] is FlowResultType.CREATE_ENTRY
    assert result1["title"] == "Volvo On Call will be removed ❌"
    assert result1["data"] == {}

    # Second flow should also succeed
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Volvo On Call will be removed ❌"
    assert result2["data"] == {}


async def test_flow_with_existing_config_entry(hass: HomeAssistant) -> None:
    """Test the config flow works even with existing config entries."""
    # Create an existing config entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Volvo On Call will be removed ❌",
        data={},
    )
    entry.add_to_hass(hass)

    # New flow should still work
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Volvo On Call will be removed ❌"
    assert result["data"] == {}
