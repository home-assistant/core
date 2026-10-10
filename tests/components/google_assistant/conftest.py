"""Fixtures for google_assistant tests."""

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
async def load_homeassistant(hass: HomeAssistant) -> None:
    """Load the homeassistant integration.

    This is needed for GoogleConfig.should_expose to work, since it relies on
    the shared exposed entities store.
    """
    assert await async_setup_component(hass, "homeassistant", {})
