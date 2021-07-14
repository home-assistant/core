"""The tests for the siren component."""
from unittest.mock import MagicMock

from homeassistant.components.siren import SirenEntity


class MockSirenEntity(SirenEntity):
    """Mock siren device to use in tests."""

    _attr_is_on = True

    def __init__(self, supported_features: int = 0) -> None:
        """Initialize mock siren entity."""
        self._attr_supported_features = supported_features


async def test_sync_turn_on(hass):
    """Test if async turn_on calls sync turn_on."""
    siren = MockSirenEntity()
    siren.hass = hass

    siren.turn_on = MagicMock()
    await siren.async_turn_on()

    assert siren.turn_on.called


async def test_sync_turn_off(hass):
    """Test if async turn_off calls sync turn_off."""
    siren = MockSirenEntity()
    siren.hass = hass

    siren.turn_off = MagicMock()
    await siren.async_turn_off()

    assert siren.turn_off.called
