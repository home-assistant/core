"""Common test helpers for the zone integration."""

import pytest

from homeassistant.components.labs import async_update_preview_feature
from homeassistant.components.zone import (
    DOMAIN,
    PREVIEW_FEATURE_IMPROVED_PRESENCE_DETECTION,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def async_set_improved_presence_detection(
    hass: HomeAssistant, enabled: bool
) -> None:
    """Set up labs and set the improved presence detection preview feature."""
    assert await async_setup_component(hass, "labs", {})
    await async_update_preview_feature(
        hass, DOMAIN, PREVIEW_FEATURE_IMPROVED_PRESENCE_DETECTION, enabled
    )


@pytest.fixture(params=[False, True], ids=["overlap", "containment"])
async def improved_presence_detection(
    hass: HomeAssistant, request: pytest.FixtureRequest
) -> bool:
    """Run the test with both zone presence detection methods."""
    await async_set_improved_presence_detection(hass, request.param)
    return request.param
