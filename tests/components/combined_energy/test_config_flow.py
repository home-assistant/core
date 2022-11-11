"""Test cases for conbined energy config flow."""
from homeassistant import config_entries
from homeassistant.components.combined_energy.const import DOMAIN
from homeassistant.core import HomeAssistant


async def test_form(hass: HomeAssistant):
    """Test that a form is created."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["errors"] == {}
