"""Test the ClimaCell config flow."""
from homeassistant import data_entry_flow
from homeassistant.components.climacell.const import (
    CONF_TIMESTEP,
    DEFAULT_TIMESTEP,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from .const import API_V3_ENTRY_DATA

from tests.common import MockConfigEntry


async def test_options_flow(
    hass: HomeAssistant, climacell_config_entry_update: None
) -> None:
    """Test options config flow for climacell."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=API_V3_ENTRY_DATA,
        source=SOURCE_USER,
        unique_id="test",
        version=1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.options[CONF_TIMESTEP] == DEFAULT_TIMESTEP
    assert CONF_TIMESTEP not in entry.data

    result = await hass.config_entries.options.async_init(entry.entry_id, data=None)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_TIMESTEP: 1}
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"][CONF_TIMESTEP] == 1
    assert entry.options[CONF_TIMESTEP] == 1
