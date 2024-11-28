"""Tests for application credentials module."""

from homeassistant.components.myuplink.application_credentials import (
    async_get_description_placeholders,
)
from homeassistant.core import HomeAssistant


async def test_placeholders(hass: HomeAssistant) -> None:
    """Test that required placeholders are returned."""
    placeholders = await async_get_description_placeholders(hass)

    assert len(placeholders) == 3
    assert "more_info_url" in placeholders
    assert "create_creds_url" in placeholders
    assert "callback_url" in placeholders
