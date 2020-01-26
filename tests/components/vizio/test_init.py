"""Tests for Vizio init."""
import pytest

from homeassistant.components.vizio.const import DOMAIN
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_setup_component

from .const import MOCK_SPEAKER_CONFIG


async def test_unload(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_bypass_setup: pytest.fixture,
) -> None:
    """Test loading component and unloading entry."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: MOCK_SPEAKER_CONFIG})
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    for entry in entries:
        assert await entry.async_unload(hass)
