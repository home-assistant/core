"""Test the Green Planet Energy config flow."""

from homeassistant import config_entries
from homeassistant.components.green_planet_energy.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Green Planet Energy"
    assert result2["data"] == {}


async def test_single_instance_allowed(hass: HomeAssistant) -> None:
    """Test that only one instance is allowed."""
    # First setup should succeed
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Second setup should abort
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
