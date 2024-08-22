"""Test the Logitech Harmony Hub activity select."""

from datetime import timedelta

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util import utcnow

from .const import ENTITY_REMOTE, ENTITY_SELECT

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_connection_state_changes(
    harmony_client,
    mock_hc,
    hass: HomeAssistant,
    mock_write_config,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure connection changes are reflected in the switch states."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # mocks start with current activity == Watch TV
    assert hass.states.is_state(ENTITY_SELECT, "Watch TV")

    harmony_client.mock_disconnection()
    await hass.async_block_till_done()

    # Entities do not immediately show as unavailable
    assert hass.states.is_state(ENTITY_SELECT, "Watch TV")

    future_time = utcnow() + timedelta(seconds=10)
    async_fire_time_changed(hass, future_time)
    await hass.async_block_till_done()
    assert hass.states.is_state(ENTITY_SELECT, STATE_UNAVAILABLE)

    harmony_client.mock_reconnection()
    await hass.async_block_till_done()

    assert hass.states.is_state(ENTITY_SELECT, "Watch TV")


async def test_options(
    mock_hc, hass: HomeAssistant, mock_write_config, mock_config_entry: MockConfigEntry
) -> None:
    """Ensure calls to the switch modify the harmony state."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # assert we have all options
    state = hass.states.get(ENTITY_SELECT)
    assert state.attributes.get("options") == [
        "power_off",
        "Nile-TV",
        "Play Music",
        "Watch TV",
    ]


async def test_select_option(
    mock_hc, hass: HomeAssistant, mock_write_config, mock_config_entry: MockConfigEntry
) -> None:
    """Ensure calls to the switch modify the harmony state."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # mocks start with current activity == Watch TV
    assert hass.states.is_state(ENTITY_REMOTE, STATE_ON)
    assert hass.states.is_state(ENTITY_SELECT, "Watch TV")

    # launch Play Music activity
    await _select_option_and_wait(hass, ENTITY_SELECT, "Play Music")
    assert hass.states.is_state(ENTITY_REMOTE, STATE_ON)
    assert hass.states.is_state(ENTITY_SELECT, "Play Music")

    # turn off harmony by selecting power_off activity
    await _select_option_and_wait(hass, ENTITY_SELECT, "power_off")
    assert hass.states.is_state(ENTITY_REMOTE, STATE_OFF)
    assert hass.states.is_state(ENTITY_SELECT, "power_off")


async def _select_option_and_wait(
    hass: HomeAssistant, entity: str, option: str
) -> None:
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: entity,
            ATTR_OPTION: option,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
