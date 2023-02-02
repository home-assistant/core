"""The tests for light platform."""

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import async_setup
from .const import LIGHT_STATE_OFF_PACKET, LIGHT_STATE_ON_PACKET, LIGHT_TEST_ENTITY_ID


async def test_entity_load(hass: HomeAssistant, mock_imazu_client):
    """Test entity load."""
    entry = await async_setup(hass)

    packet = bytes.fromhex(LIGHT_STATE_OFF_PACKET)
    await mock_imazu_client.async_receive_packet(packet)
    await hass.async_block_till_done()

    entity_registry = hass.helpers.entity_registry.async_get(hass)
    entities = hass.helpers.entity_registry.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    )
    assert len(entities) == 1


async def test_entity_state_changed(hass: HomeAssistant, mock_imazu_client):
    """Test for state the changed."""
    await async_setup(hass)

    off_packet = bytes.fromhex(LIGHT_STATE_OFF_PACKET)
    await mock_imazu_client.async_receive_packet(off_packet)
    await hass.async_block_till_done()
    # Assert
    state = hass.states.get(LIGHT_TEST_ENTITY_ID)
    assert state and state.state == "off"
    # Changed
    on_packet = bytes.fromhex(LIGHT_STATE_ON_PACKET)
    await mock_imazu_client.async_receive_packet(on_packet)
    await hass.async_block_till_done()
    # Assert
    state = hass.states.get(LIGHT_TEST_ENTITY_ID)
    assert state and state.state == "on"


async def test_entity_state_not_changed(hass: HomeAssistant, mock_imazu_client):
    """Test for state the not changed."""
    await async_setup(hass)

    off_packet = bytes.fromhex(LIGHT_STATE_OFF_PACKET)
    await mock_imazu_client.async_receive_packet(off_packet)
    await hass.async_block_till_done()
    # Assert
    state = hass.states.get(LIGHT_TEST_ENTITY_ID)
    assert state and state.state == "off"
    # Not changed
    off_packet = bytes.fromhex(LIGHT_STATE_OFF_PACKET)
    await mock_imazu_client.async_receive_packet(off_packet)
    await hass.async_block_till_done()
    # Assert
    state = hass.states.get(LIGHT_TEST_ENTITY_ID)
    assert state and state.state == "off"


async def test_turn_on(hass, mock_imazu_client):
    """Test the light turns of successfully."""
    await async_setup(hass)
    off_packet = bytes.fromhex(LIGHT_STATE_OFF_PACKET)
    await mock_imazu_client.async_receive_packet(off_packet)
    await hass.async_block_till_done()
    # Act
    await hass.services.async_call(
        "light", "turn_on", {ATTR_ENTITY_ID: LIGHT_TEST_ENTITY_ID}, blocking=True
    )
    on_packet = bytes.fromhex(LIGHT_STATE_ON_PACKET)
    await mock_imazu_client.async_receive_packet(on_packet)
    await hass.async_block_till_done()
    # Assert
    state = hass.states.get(LIGHT_TEST_ENTITY_ID)
    assert state.state == "on"


async def test_turn_off(hass, mock_imazu_client):
    """Test the light turns of successfully."""
    await async_setup(hass)
    on_packet = bytes.fromhex(LIGHT_STATE_ON_PACKET)
    await mock_imazu_client.async_receive_packet(on_packet)
    await hass.async_block_till_done()
    # Act
    await hass.services.async_call(
        "light", "turn_off", {ATTR_ENTITY_ID: LIGHT_TEST_ENTITY_ID}, blocking=True
    )
    off_packet = bytes.fromhex(LIGHT_STATE_OFF_PACKET)
    await mock_imazu_client.async_receive_packet(off_packet)
    await hass.async_block_till_done()
    # Assert
    state = hass.states.get(LIGHT_TEST_ENTITY_ID)
    assert state.state == "off"
