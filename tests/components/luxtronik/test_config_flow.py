"""Define tests for the Luxtronik Heatpump config flow."""


from homeassistant import data_entry_flow
from homeassistant.components.luxtronik.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CONFIG = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 8889,
}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER


async def test_form_duplicated_id(hass: HomeAssistant) -> None:
    """Test setting up duplicated entry."""

    config_entry = MockConfigEntry(
        data=CONFIG,
        domain=DOMAIN,
        unique_id="luxtronik_unique_id",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
