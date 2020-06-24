"""Binary sensor tests."""
from zoneminder.monitor import MonitorState

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.zoneminder import const
from homeassistant.const import CONF_COMMAND_OFF, CONF_COMMAND_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test switch entities."""
    await async_setup_component(hass, "homeassistant", {})
    await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {
            SWITCH_DOMAIN: [
                {
                    "platform": const.DOMAIN,
                    CONF_COMMAND_ON: MonitorState.NODECT.value,
                    CONF_COMMAND_OFF: MonitorState.MONITOR.value,
                },
                {
                    "platform": const.DOMAIN,
                    CONF_COMMAND_ON: MonitorState.NONE.value,
                    CONF_COMMAND_OFF: MonitorState.MOCORD.value,
                },
            ]
        },
    )
