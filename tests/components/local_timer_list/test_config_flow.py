"""Test the Local Timer list config flow."""

from homeassistant.components.local_timer_list.const import CONF_TIMER_LIST_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_user_flow_creates_entity(hass: HomeAssistant) -> None:
    """Test the user config flow creates an entry and a named timer list entity."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TIMER_LIST_NAME: "Kitchen"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Kitchen"
    assert result["data"] == {CONF_TIMER_LIST_NAME: "Kitchen"}

    state = hass.states.get("timer_list.kitchen")
    assert state is not None
    assert state.state == "0"
