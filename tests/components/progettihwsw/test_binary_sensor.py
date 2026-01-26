"""Test the ProgettiHWSW Automation binary sensor."""

from unittest.mock import MagicMock, patch

from homeassistant.components.progettihwsw.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_binary_sensor_setup(hass: HomeAssistant) -> None:
    """Test the binary sensor setup and state."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.10",
            CONF_PORT: 80,
            "relay_count": 0,
            "input_count": 1,
        },
    )
    entry.add_to_hass(hass)

    # Mock API response for inputs
    # Input 1 is "up" (True)
    mock_inputs = [True]

    with (
        patch(
            "homeassistant.components.progettihwsw.ProgettiHWSWAPI.check_board",
            return_value=True,
        ),
        patch(
            "homeassistant.components.progettihwsw.ProgettiHWSWAPI.get_inputs",
            return_value=mock_inputs,
        ),
        patch(
            "homeassistant.components.progettihwsw.ProgettiHWSWAPI.get_switches",
            return_value=[],
        ),
        patch(
            "ProgettiHWSW.api.API.request",
            return_value="<response></response>",
        ),
        patch("homeassistant.components.progettihwsw.setup_input") as mock_setup_input,
    ):
        # Mock setup_input to return an Input object with id 1
        mock_input_obj = MagicMock()
        mock_input_obj.id = 1
        mock_setup_input.return_value = mock_input_obj

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Check entity unique_id and state
        entity_id = "binary_sensor.input_1"
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "on"

        # Verify unique_id generation logic indirectly via registry or by checking the entity attribute if accessible
        # But we can check if the entity exists in registry
        entity_registry = er.async_get(hass)
        entry_entity = entity_registry.async_get(entity_id)
        assert entry_entity
        assert entry_entity.unique_id == f"{entry.entry_id}_192.168.1.10_input_1"

        # Verify is_on property logic (id - 1)
        # The coordinator data is [True] (index 0)
        # The sensor id is 1. 1 - 1 = 0. So it should access index 0.
        # This is implicitly verified by state being "on".
