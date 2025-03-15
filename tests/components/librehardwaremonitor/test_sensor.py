"""Test the LibreHardwareMonitor sensor."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant

from . import init_integration


async def test_sensors_are_created(
    hass: HomeAssistant, mock_lhm_client: AsyncMock
) -> None:
    """Test sensors are created."""
    entity_id = "sensor.amd_ryzen_7_7800x3d_package_temperature"
    await init_integration(hass)

    state = hass.states.get(entity_id)

    assert state
    assert state.name == "AMD Ryzen 7 7800X3D Package Temperature"
    assert state.state == "39.4"
    assert state.attributes
    assert state.attributes.get("min_value") == "37.4"
    assert state.attributes.get("max_value") == "73.0"
    assert state.attributes.get("unit_of_measurement") == "°C"
