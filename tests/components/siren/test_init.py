"""The tests for the siren component."""
from unittest.mock import MagicMock

from homeassistant.components.siren import SirenEntity


class MockSirenEntity(SirenEntity):
    """Mock siren device to use in tests."""

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return 0


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


async def test_sync_set_volume_level(hass):
    """Test if async set_volume_level calls sync set_volume_level."""
    siren = MockSirenEntity()
    siren.hass = hass

    siren.set_volume_level = MagicMock()
    await siren.async_set_volume_level(0.5)

    assert siren.set_volume_level.called


async def test_sync_set_default_tone(hass):
    """Test if async set_default_tone calls sync set_default_tone."""
    siren = MockSirenEntity()
    siren.hass = hass

    siren.set_default_tone = MagicMock()
    await siren.async_set_default_tone("fire")

    assert siren.set_default_tone.called


async def test_sync_set_default_duration(hass):
    """Test if async set_default_duration calls sync set_default_duration."""
    siren = MockSirenEntity()
    siren.hass = hass

    siren.set_default_duration = MagicMock()
    await siren.async_set_default_duration(1)

    assert siren.set_default_duration.called
