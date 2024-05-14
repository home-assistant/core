"""Test the Aladdin Connect model class."""

from homeassistant.components.aladdin_connect.model import DoorDevice
from homeassistant.core import HomeAssistant


async def test_model(hass: HomeAssistant) -> None:
    """Test model for Aladdin Connect Model."""
    test_values = {
        "device_id": "1",
        "door_number": "2",
        "name": "my door",
        "status": "good",
    }
    result2 = DoorDevice(test_values)
    assert result2["device_id"] == "1"
    assert result2["door_number"] == "2"
    assert result2["name"] == "my door"
    assert result2["status"] == "good"
