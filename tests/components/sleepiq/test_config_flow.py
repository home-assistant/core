"""Tests for the SleepIQ config flow."""

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.sleepiq.const import DOMAIN


async def test_show_set_form(hass):
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=None
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
