"""Test the Ziggo Next config flow."""
from homeassistant import data_entry_flow
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        "ziggo_next", context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
