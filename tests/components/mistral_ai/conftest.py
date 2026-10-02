"""Fixtures for Mistral AI tests."""

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
async def setup_ha(hass: HomeAssistant) -> None:
    """Set up the homeassistant component (exposed entities registry)."""
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()
