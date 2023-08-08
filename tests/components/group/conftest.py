"""group conftest."""
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture(autouse=True)
async def setup_homeassistant(hass: HomeAssistant):
    """Set up the homeassistant integration."""
    await async_setup_component(hass, "homeassistant", {})
