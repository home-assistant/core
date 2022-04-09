"""Define tests for the ATEN PE config flow."""

from homeassistant import data_entry_flow
from homeassistant.components.aten_pe.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER
