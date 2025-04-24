"""Test the switchbot switches."""

from collections.abc import Callable
from unittest.mock import patch

from homeassistant.components.switch import STATE_ON
from homeassistant.core import HomeAssistant, State

from . import WOHAND_SERVICE_INFO

from tests.common import MockConfigEntry, mock_restore_cache
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_switchbot_switch_with_restore_state(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test that Switchbot Switch restores state correctly after reboot."""
    inject_bluetooth_service_info(hass, WOHAND_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="bot")
    entity_id = "switch.test_name"

    mock_restore_cache(
        hass,
        [
            State(
                entity_id,
                STATE_ON,
                {"last_run_success": True},
            )
        ],
    )

    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.switchbot.switch.switchbot.Switchbot.switch_mode",
        return_value=False,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_ON
        assert state.attributes["last_run_success"] is True
