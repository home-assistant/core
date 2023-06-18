"""Test integration platform helpers."""
from unittest.mock import Mock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.integration_platform import (
    async_process_integration_platform_for_component,
    async_process_integration_platforms,
)
from homeassistant.setup import ATTR_COMPONENT, EVENT_COMPONENT_LOADED

from tests.common import mock_platform


async def test_process_integration_platforms(hass: HomeAssistant) -> None:
    """Test processing integrations."""
    loaded_platform = Mock()
    mock_platform(hass, "loaded.platform_to_check", loaded_platform)
    hass.config.components.add("loaded")

    event_platform = Mock()
    mock_platform(hass, "event.platform_to_check", event_platform)

    processed = []

    async def _process_platform(hass, domain, platform):
        """Process platform."""
        processed.append((domain, platform))

    await async_process_integration_platforms(
        hass, "platform_to_check", _process_platform
    )

    assert len(processed) == 1
    assert processed[0][0] == "loaded"
    assert processed[0][1] == loaded_platform

    hass.bus.async_fire(EVENT_COMPONENT_LOADED, {ATTR_COMPONENT: "event"})
    await hass.async_block_till_done()

    assert len(processed) == 2
    assert processed[1][0] == "event"
    assert processed[1][1] == event_platform

    # Verify we only process the platform once if we call it manually
    await async_process_integration_platform_for_component(hass, "event")
    assert len(processed) == 2


async def test_process_integration_platforms_none_loaded(hass: HomeAssistant) -> None:
    """Test processing integrations with none loaded."""
    # Verify we can call async_process_integration_platform_for_component
    # when there are none loaded and it does not throw
    await async_process_integration_platform_for_component(hass, "any")


async def test_broken_integration(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test handling an integration with a broken or missing manifest."""
    Mock()
    hass.config.components.add("loaded")

    event_platform = Mock()
    mock_platform(hass, "event.platform_to_check", event_platform)

    processed = []

    async def _process_platform(hass, domain, platform):
        """Process platform."""
        processed.append((domain, platform))

    await async_process_integration_platforms(
        hass, "platform_to_check", _process_platform
    )

    assert len(processed) == 0
    assert "Error importing integration loaded for platform_to_check" in caplog.text
