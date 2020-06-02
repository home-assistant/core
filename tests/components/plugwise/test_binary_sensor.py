"""Tests for the Plugwise binary_sensor integration."""

from tests.components.plugwise.common import async_init_integration


async def test_anna_climate_sensor_entities(hass, mock_smile_anna):
    """Test creation of climate related sensor entities."""
    await async_init_integration(hass, mock_smile_anna)

    state = hass.states.get("binary_sensor.auxiliary_slave_boiler_state")
    assert str(state.state) == "off"

    state = hass.states.get("binary_sensor.auxiliary_dhw_state")
    assert str(state.state) == "off"
