"""Test the NZBGet sensors."""
from . import init_integration

async def test_sensors(hass) -> None:
    """Test the creation and values of the sensors."""
    entry = await init_integration(hass)
