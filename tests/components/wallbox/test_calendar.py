"""Test Wallbox calendar component."""

from freezegun.api import FrozenDateTimeFactory

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_calendar(
    hass: HomeAssistant, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Test for successfully setting up the Wallbox calendar."""
