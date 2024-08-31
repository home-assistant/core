"""The tests for the persistent notification component."""

import pytest

import homeassistant.components.persistent_notification as pn
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
async def setup_integration(hass):
    """Set up persistent notification integration."""
    assert await async_setup_component(hass, pn.DOMAIN, {})
