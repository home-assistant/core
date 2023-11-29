"""Test the OpenAQ config flow."""

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.openAQ.const import DOMAIN
from homeassistant.core import HomeAssistant


async def test_form_shows_initial(hass: HomeAssistant):
    """Test that the initial form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
