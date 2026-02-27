"""Tests for Trinnov Altitude number platform."""

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import MOCK_ID

from tests.common import MockConfigEntry

ENTITY_ID = f"number.trinnov_altitude_{MOCK_ID}_volume"


async def test_entity(
    hass: HomeAssistant,
    mock_device,
    mock_integration: MockConfigEntry,
) -> None:
    """Test volume number entity exists."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None


async def test_set_value(
    hass: HomeAssistant,
    mock_device,
    mock_integration: MockConfigEntry,
) -> None:
    """Test setting volume number value."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: ENTITY_ID, "value": -40.5},
        blocking=True,
    )
    mock_device.volume_set.assert_called_once_with(-40.5)
