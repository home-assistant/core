"""Test the Volvo On Call config flow."""

from homeassistant import config_entries
from homeassistant.components.volvooncall.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get an abort with deprecation message."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "deprecated"


async def test_flow_aborts_with_existing_config_entry(hass: HomeAssistant) -> None:
    """Test the config flow aborts even with existing config entries."""
    # Create an existing config entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Volvo On Call",
        data={},
    )
    entry.add_to_hass(hass)

    # New flow should still abort
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "deprecated"
