"""Tests for the PowerShades cover platform."""

from pyowershades import OP_JOG_STOP, OP_SET_POSITION, build_set_position_payload

from homeassistant.components.powershades import coordinator as coordinator_module
from homeassistant.components.powershades.const import DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_IP, TEST_NAME

from tests.common import MockConfigEntry

ENTITY_ID = "cover.powershade_bedroom_shade"


async def test_cover_initial_state(hass: HomeAssistant, config_entry) -> None:
    """The cover reflects the position reported by the device."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "open"
    assert state.attributes["current_position"] == 50
    assert state.attributes[ATTR_FRIENDLY_NAME] == "PowerShade Bedroom Shade"


async def test_cover_closed_state(hass: HomeAssistant, config_entry) -> None:
    """A position of 0 is reported as closed."""
    coordinator = config_entry.runtime_data
    coordinator.async_set_updated_data(
        coordinator_module.PowerShadesData(position=0, target_position=None)
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == "closed"


async def test_cover_unknown_position_state(hass: HomeAssistant, config_entry) -> None:
    """An unknown position is reported as neither open nor closed."""
    coordinator = config_entry.runtime_data
    coordinator.async_set_updated_data(
        coordinator_module.PowerShadesData(position=None, target_position=None)
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == "unknown"


async def test_cover_opening_state(hass: HomeAssistant, config_entry) -> None:
    """A target above the current position is reported as opening."""
    coordinator = config_entry.runtime_data
    coordinator.async_set_updated_data(
        coordinator_module.PowerShadesData(position=50, target_position=100)
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == "opening"


async def test_cover_closing_state(hass: HomeAssistant, config_entry) -> None:
    """A target below the current position is reported as closing."""
    coordinator = config_entry.runtime_data
    coordinator.async_set_updated_data(
        coordinator_module.PowerShadesData(position=50, target_position=0)
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == "closing"


async def test_open_cover(hass: HomeAssistant, config_entry) -> None:
    """Opening the cover sets the position to 100."""
    coordinator = config_entry.runtime_data
    await hass.services.async_call(
        "cover", "open_cover", {"entity_id": ENTITY_ID}, blocking=True
    )

    coordinator.connection.async_request.assert_any_call(
        OP_SET_POSITION, build_set_position_payload(100)
    )


async def test_close_cover(hass: HomeAssistant, config_entry) -> None:
    """Closing the cover sets the position to 0."""
    coordinator = config_entry.runtime_data
    await hass.services.async_call(
        "cover", "close_cover", {"entity_id": ENTITY_ID}, blocking=True
    )

    coordinator.connection.async_request.assert_any_call(
        OP_SET_POSITION, build_set_position_payload(0)
    )


async def test_stop_cover(hass: HomeAssistant, config_entry) -> None:
    """Stopping the cover sends the jog stop command."""
    coordinator = config_entry.runtime_data
    await hass.services.async_call(
        "cover", "stop_cover", {"entity_id": ENTITY_ID}, blocking=True
    )

    coordinator.connection.async_request.assert_any_call(OP_JOG_STOP, b"")


async def test_set_cover_position(hass: HomeAssistant, config_entry) -> None:
    """Setting a specific position sends that position to the device."""
    coordinator = config_entry.runtime_data
    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": ENTITY_ID, "position": 30},
        blocking=True,
    )

    coordinator.connection.async_request.assert_any_call(
        OP_SET_POSITION, build_set_position_payload(30)
    )


async def test_unique_id_without_serial_falls_back_to_entry_id(
    hass: HomeAssistant, mock_connection
) -> None:
    """Without a known serial number, the unique ID is based on the entry ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"ip": TEST_IP, "name": TEST_NAME, "model": 1},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = er.async_get(hass).async_get(ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.unique_id == f"{DOMAIN}_{entry.entry_id}_cover"
