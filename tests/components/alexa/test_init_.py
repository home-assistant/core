"""Tests for alexa."""

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


# 1) Not configured at all: `async_setup` should return True (no-op success)
@pytest.mark.asyncio
async def test_alexa_setup_returns_true_when_not_configured(
    hass: HomeAssistant,
) -> None:
    """Test that alexa setup returns True when not configured."""
    assert await async_setup_component(hass, "alexa", {}) is True


# 2) Configured with minimal YAML sections: still returns True
@pytest.mark.asyncio
async def test_alexa_setup_returns_true_with_minimal_config(
    hass: HomeAssistant,
) -> None:
    """Test that alexa setup returns True with minimal configuration."""
    config = {
        "alexa": {
            # Minimal: just an empty smart_home section exercises the configured path.
            "smart_home": {},
            # Optional: include flash_briefings to exercise that branch too
            # "flash_briefings": {"weather": [{"title": "t", "text": "hello"}]},
        }
    }
    assert await async_setup_component(hass, "alexa", config) is True
