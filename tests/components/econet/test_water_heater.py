"""Test EcoNet water heaters."""

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock

from pyeconet.errors import InvalidResponseFormat
import pytest

from homeassistant.const import ATTR_FRIENDLY_NAME, Platform
from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.parametrize("platform", [Platform.WATER_HEATER])


async def test_water_heater_name(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    mock_api: MagicMock,
) -> None:
    """Water heaters retain their device name and entity ID."""
    mock_api.get_dynamic_action.side_effect = InvalidResponseFormat

    await setup_integration()

    state = hass.states.get("water_heater.gas_water_heater")
    assert state is not None
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Gas Water Heater"
