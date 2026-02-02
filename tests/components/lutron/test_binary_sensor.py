"""Test Lutron binary sensor platform."""

from unittest.mock import MagicMock

from pylutron import OccupancyGroup

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_binary_sensor_setup(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test binary sensor setup."""
    mock_config_entry.add_to_hass(hass)

    occ_group = mock_lutron.areas[0].occupancy_group
    occ_group.state = OccupancyGroup.State.VACANT

    assert await async_setup_component(hass, "lutron", {})
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_occupancy_occupancy")
    assert state is not None
    assert state.state == STATE_OFF


async def test_binary_sensor_update(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test binary sensor update."""
    mock_config_entry.add_to_hass(hass)

    occ_group = mock_lutron.areas[0].occupancy_group
    occ_group.state = OccupancyGroup.State.VACANT

    assert await async_setup_component(hass, "lutron", {})
    await hass.async_block_till_done()

    entity_id = "binary_sensor.test_occupancy_occupancy"
    assert hass.states.get(entity_id).state == STATE_OFF

    # Simulate update
    occ_group.state = OccupancyGroup.State.OCCUPIED
    callback = occ_group.subscribe.call_args[0][0]
    callback(occ_group, None, None, None)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ON
