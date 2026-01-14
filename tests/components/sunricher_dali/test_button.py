"""Test the Sunricher DALI button platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant


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
        {ATTR_ENTITY_ID: "button.dimmer_0000_02"},
        blocking=True,
    )

    mock_devices[0].identify.assert_called_once()
