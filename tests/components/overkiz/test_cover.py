"""Tests for Overkiz cover entities."""

from unittest.mock import patch

from pyoverkiz.enums import OverkizCommand
import pytest

from homeassistant.components.overkiz.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import load_setup_fixture

from tests.common import MockConfigEntry


@pytest.mark.parametrize("mock_setup_fixture", ["overkiz/setup_cover_with_tilt.json"])
async def test_set_cover_position_and_tilt_position(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_setup_fixture: str
) -> None:
    """Test set_cover_position_and_tilt_position service."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("pyoverkiz.client.OverkizClient.login", return_value=True),
        patch(
            "pyoverkiz.client.OverkizClient.get_setup",
            return_value=load_setup_fixture(mock_setup_fixture),
        ),
        patch(
            "pyoverkiz.client.OverkizClient.get_scenarios",
            return_value=[],
        ),
        patch(
            "pyoverkiz.client.OverkizClient.register_event_listener",
            return_value="1234",
        ),
        patch(
            "pyoverkiz.client.OverkizClient.fetch_events",
            return_value=[],
        ),
        patch("pyoverkiz.client.OverkizClient.execute_command") as mock_execute_command,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "cover.venetian_blind"

        # Position 50, Tilt 20
        # Expected sent: Closure 50 (100-50), Orientation 80 (100-20)
        await hass.services.async_call(
            DOMAIN,
            "set_cover_position_and_tilt_position",
            {
                ATTR_ENTITY_ID: entity_id,
                "position": 50,
                "tilt_position": 20,
            },
            blocking=True,
        )

        assert mock_execute_command.call_count == 1
        call_args = mock_execute_command.call_args

        # Check positional arguments
        assert call_args.args[0] == "io://****-****-6867/12345678"
        command = call_args.args[1]
        assert command.name == OverkizCommand.SET_CLOSURE_AND_ORIENTATION
        assert command.parameters == [50, 80]
        assert call_args.args[2] == "Home Assistant"
