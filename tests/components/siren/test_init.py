"""The tests for the siren component."""
from unittest.mock import MagicMock

import pytest

from homeassistant.components.siren import SirenEntity, process_turn_on_params
from homeassistant.components.siren.const import SUPPORT_TONES


class MockSirenEntity(SirenEntity):
    """Mock siren device to use in tests."""

    _attr_is_on = True

    def __init__(self, supported_features=0, available_tones=None):
        """Initialize mock siren entity."""
        self._attr_supported_features = supported_features
        self._attr_available_tones = available_tones


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


async def test_no_available_tones(hass):
    """Test ValueError when siren advertises tones but has no available_tones."""
    siren = MockSirenEntity(SUPPORT_TONES)
    siren.hass = hass
    with pytest.raises(ValueError):
        process_turn_on_params(siren, {"tone": "test"})


async def test_missing_tones(hass):
    """Test ValueError when setting a tone that is missing from available_tones."""
    siren = MockSirenEntity(SUPPORT_TONES, ["a", "b"])
    siren.hass = hass
    with pytest.raises(ValueError):
        process_turn_on_params(siren, {"tone": "test"})
