"""Test the ProgettiHWSW Automation switch."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.progettihwsw.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_switch_setup_and_control(hass: HomeAssistant) -> None:
    """Test the switch setup, state, and control."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.10",
            CONF_PORT: 80,
            "relay_count": 1,
            "input_count": 0,
            "relay_1": "bistable",
        },
    )
    entry.add_to_hass(hass)

    # Mock API response for switches
    # Relay 1 is "on" (True)
    mock_switches = [True]

    with (
        patch(
            "homeassistant.components.progettihwsw.ProgettiHWSWAPI.check_board",
            return_value=True,
        ),
        patch(
            "homeassistant.components.progettihwsw.ProgettiHWSWAPI.get_switches",
            return_value=mock_switches,
        ),
        patch(
            "homeassistant.components.progettihwsw.ProgettiHWSWAPI.get_inputs",
            return_value=[],
        ),
        patch(
            "ProgettiHWSW.api.API.request",
            return_value="<response></response>",
        ),
        patch(
            "homeassistant.components.progettihwsw.switch.setup_switch"
        ) as mock_setup_switch,
    ):
        # Mock setup_switch to return a Relay object with id 1
        mock_relay_obj = MagicMock()
        mock_relay_obj.id = 1
        # Make control and toggle async methods
        mock_relay_obj.control = AsyncMock()
        mock_relay_obj.toggle = AsyncMock()
        mock_setup_switch.return_value = mock_relay_obj

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Check entity unique_id and state
        entity_id = "switch.relay_1"
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "on"

        # Verify unique_id generation logic
        entity_registry = er.async_get(hass)
        entry_entity = entity_registry.async_get(entity_id)
        assert entry_entity
        assert entry_entity.unique_id == f"{entry.entry_id}_192.168.1.10_relay_1"

        # Test async_turn_off
        await hass.services.async_call(
            "switch", "turn_off", {"entity_id": entity_id}, blocking=True
        )
        mock_relay_obj.control.assert_called_with(False)

        # Test async_turn_on
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": entity_id}, blocking=True
        )
        mock_relay_obj.control.assert_called_with(True)

        # Test async_toggle
        await hass.services.async_call(
            "switch", "toggle", {"entity_id": entity_id}, blocking=True
        )
        mock_relay_obj.toggle.assert_called_once()
