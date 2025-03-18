"""PurpleAir options flow tests."""

from homeassistant.components.purpleair.const import CONF_SETTINGS
from homeassistant.const import CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import CONF_DATA, CONF_FLOW_ID, CONF_STEP_ID, CONF_TYPE


async def test_options_settings(
    hass: HomeAssistant, config_entry, setup_config_entry
) -> None:
    """Test options setting flow."""

    # Options init
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_SETTINGS

    # Settings
    result = await hass.config_entries.options.async_configure(
        result[CONF_FLOW_ID], user_input={CONF_SHOW_ON_MAP: True}
    )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.CREATE_ENTRY
    assert result[CONF_DATA] == {
        CONF_SHOW_ON_MAP: True,
    }
