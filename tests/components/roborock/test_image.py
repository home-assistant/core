"""Test Roborock Image platform."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_image(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    """Check that the correct number of images set up correctly."""
    assert len(hass.states.async_all("image")) == 4
