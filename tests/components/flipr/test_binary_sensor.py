"""Test the Flipr binary sensor."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_flipr_client: AsyncMock,
) -> None:
    """Test the creation and values of the Flipr binary sensors."""

    await setup_integration(hass, mock_config_entry)

    # Check entity unique_id value that is generated in FliprEntity base class.
    entity = entity_registry.async_get("binary_sensor.flipr_myfliprid_ph_status")
    assert entity.unique_id == "myfliprid-ph_status"

    state = hass.states.get("binary_sensor.flipr_myfliprid_ph_status")
    assert state
    assert state.state == "on"  # Alert is on for binary sensor

    state = hass.states.get("binary_sensor.flipr_myfliprid_chlorine_status")
    assert state
    assert state.state == "off"
