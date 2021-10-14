"""Test the button significant change platform."""
from homeassistant.components.button.significant_change import (
    async_check_significant_change,
)
from homeassistant.core import HomeAssistant


async def test_significant_change(hass: HomeAssistant) -> None:
    """Detect button significant change."""
    assert not async_check_significant_change(
        hass, "2021-01-01T23:59:59+00:00", {}, "2021-01-01T23:59:59+00:00", {}
    )
    assert async_check_significant_change(
        hass, "2021-01-01T23:59:59+00:00", {}, "2021-01-02T01:59:59+00:00", {}
    )
