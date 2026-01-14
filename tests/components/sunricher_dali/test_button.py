"""Test the Sunricher DALI button platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import trigger_availability_callback

TEST_BUTTON_ENTITY_ID = "button.dimmer_0000_02"


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify which platforms to test."""
    return [Platform.BUTTON]


@pytest.mark.usefixtures("init_integration")
async def test_identify_button_press(
    hass: HomeAssistant,
    mock_devices: list[MagicMock],
) -> None:
    """Test pressing the identify button calls device.identify()."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: TEST_BUTTON_ENTITY_ID},
        blocking=True,
    )

    mock_devices[0].identify.assert_called_once()


@pytest.mark.usefixtures("init_integration")
async def test_identify_button_entity_attributes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the identify button entity has correct attributes."""
    entity_entry = entity_registry.async_get(TEST_BUTTON_ENTITY_ID)

    assert entity_entry is not None
    assert entity_entry.original_device_class == "identify"
    assert entity_entry.entity_category == "config"


@pytest.mark.usefixtures("init_integration")
async def test_identify_button_availability(
    hass: HomeAssistant,
    mock_devices: list[MagicMock],
) -> None:
    """Test availability changes are reflected in button state."""
    trigger_availability_callback(mock_devices[0], False)
    await hass.async_block_till_done()
    assert (state := hass.states.get(TEST_BUTTON_ENTITY_ID))
    assert state.state == "unavailable"

    trigger_availability_callback(mock_devices[0], True)
    await hass.async_block_till_done()
    assert (state := hass.states.get(TEST_BUTTON_ENTITY_ID))
    assert state.state != "unavailable"
