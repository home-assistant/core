"""Test the ProgettiHWSW Automation setup."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.progettihwsw.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test the platforms of a board are set up."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.1",
            CONF_PORT: 80,
            "relay_count": 1,
            "input_count": 1,
            "relay_1": "bistable",
        },
    )
    entry.add_to_hass(hass)

    relay = MagicMock(id=1)
    board_input = MagicMock(id=1)
    api = MagicMock()
    api.check_board = AsyncMock(return_value=True)
    api.get_switches = AsyncMock(return_value={1: True})
    api.get_inputs = AsyncMock(return_value={1: False})
    api.get_relay = MagicMock(return_value=relay)
    api.get_input = MagicMock(return_value=board_input)

    with patch(
        "homeassistant.components.progettihwsw.ProgettiHWSWAPI", return_value=api
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("switch.relay_1").state == "on"
    assert hass.states.get("binary_sensor.input_1").state == "off"
