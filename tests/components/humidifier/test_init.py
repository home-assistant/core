"""The tests for the humidifier component."""
from unittest.mock import MagicMock

from homeassistant.components.humidifier import HumidifierEntity


class MockHumidifierEntity(HumidifierEntity):
    """Mock Humidifier device to use in tests."""

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return 0


async def test_sync_turn_on(hass):
    """Test if async turn_on calls sync turn_on."""
    humidifier = MockHumidifierEntity()
    humidifier.hass = hass

    humidifier.turn_on = MagicMock()
    await humidifier.async_turn_on()

    assert humidifier.turn_on.called


async def test_sync_turn_off(hass):
    """Test if async turn_off calls sync turn_off."""
    humidifier = MockHumidifierEntity()
    humidifier.hass = hass

    humidifier.turn_off = MagicMock()
    await humidifier.async_turn_off()

    assert humidifier.turn_off.called
