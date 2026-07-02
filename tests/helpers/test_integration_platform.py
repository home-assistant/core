"""Test integration platform helpers."""

import asyncio
from collections.abc import Callable
from types import ModuleType
from typing import Any
from unittest.mock import Mock, patch

import pytest

from homeassistant import loader
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.integration_platform import (
    LazyIntegrationPlatforms,
    async_process_integration_platforms,
)
from homeassistant.setup import ATTR_COMPONENT

from tests.common import MockModule, mock_integration, mock_platform


async def test_process_integration_platforms_with_wait(hass: HomeAssistant) -> None:
    """Test processing integrations."""
    loaded_platform = Mock()
    mock_platform(hass, "loaded.platform_to_check", loaded_platform)
    hass.config.components.add("loaded")

    event_platform = Mock()
    mock_platform(hass, "event.platform_to_check", event_platform)

    processed = []

    async def _process_platform(
        hass: HomeAssistant, domain: str, platform: Any
    ) -> None:
        """Process platform."""
        processed.append((domain, platform))

    await async_process_integration_platforms(
        hass, "platform_to_check", _process_platform, wait_for_platforms=True
    )
    # No block till done here, we want to make sure it waits for the platform

    assert len(processed) == 1
    assert processed[0][0] == "loaded"
    assert processed[0][1] == loaded_platform

    hass.bus.async_fire(EVENT_COMPONENT_LOADED, {ATTR_COMPONENT: "event"})
    await hass.async_block_till_done()

    assert len(processed) == 2
    assert processed[1][0] == "event"
    assert processed[1][1] == event_platform

    hass.bus.async_fire(EVENT_COMPONENT_LOADED, {ATTR_COMPONENT: "event"})
    await hass.async_block_till_done()

    # Firing again should not check again
    assert len(processed) == 2


async def test_process_integration_platforms(hass: HomeAssistant) -> None:
    """Test processing integrations."""
    loaded_platform = Mock()
    mock_platform(hass, "loaded.platform_to_check", loaded_platform)
    hass.config.components.add("loaded")

    event_platform = Mock()
    mock_platform(hass, "event.platform_to_check", event_platform)

    processed = []

    async def _process_platform(
        hass: HomeAssistant, domain: str, platform: Any
    ) -> None:
        """Process platform."""
        processed.append((domain, platform))

    await async_process_integration_platforms(
        hass, "platform_to_check", _process_platform
    )
    await hass.async_block_till_done()

    assert len(processed) == 1
    assert processed[0][0] == "loaded"
    assert processed[0][1] == loaded_platform

    hass.bus.async_fire(EVENT_COMPONENT_LOADED, {ATTR_COMPONENT: "event"})
    await hass.async_block_till_done()

    assert len(processed) == 2
    assert processed[1][0] == "event"
    assert processed[1][1] == event_platform

    hass.bus.async_fire(EVENT_COMPONENT_LOADED, {ATTR_COMPONENT: "event"})
    await hass.async_block_till_done()

    # Firing again should not check again
    assert len(processed) == 2


async def test_process_integration_platforms_import_fails(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test processing integrations when one fails to import."""
    loaded_platform = Mock()
    mock_platform(hass, "loaded.platform_to_check", loaded_platform)
    hass.config.components.add("loaded")

    event_platform = Mock()
    mock_platform(hass, "event.platform_to_check", event_platform)

    processed = []

    async def _process_platform(
        hass: HomeAssistant, domain: str, platform: Any
    ) -> None:
        """Process platform."""
        processed.append((domain, platform))

    loaded_integration = await loader.async_get_integration(hass, "loaded")
    with patch.object(
        loaded_integration, "async_get_platform", side_effect=ImportError
    ):
        await async_process_integration_platforms(
            hass, "platform_to_check", _process_platform
        )
        await hass.async_block_till_done()

    assert len(processed) == 0
    assert "Error importing platform_to_check platform for loaded" in caplog.text

    hass.bus.async_fire(EVENT_COMPONENT_LOADED, {ATTR_COMPONENT: "event"})
    await hass.async_block_till_done()

    assert len(processed) == 1
    assert processed[0][0] == "event"
    assert processed[0][1] == event_platform

    hass.bus.async_fire(EVENT_COMPONENT_LOADED, {ATTR_COMPONENT: "event"})
    await hass.async_block_till_done()

    # Firing again should not check again
    assert len(processed) == 1


async def test_process_integration_platforms_import_fails_after_registered(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test processing integrations when one fails to import."""
    loaded_platform = Mock()
    mock_platform(hass, "loaded.platform_to_check", loaded_platform)
    hass.config.components.add("loaded")

    event_platform = Mock()
    mock_platform(hass, "event.platform_to_check", event_platform)

    processed = []

    async def _process_platform(
        hass: HomeAssistant, domain: str, platform: Any
    ) -> None:
        """Process platform."""
        processed.append((domain, platform))

    await async_process_integration_platforms(
        hass, "platform_to_check", _process_platform
    )
    await hass.async_block_till_done()

    assert len(processed) == 1
    assert processed[0][0] == "loaded"
    assert processed[0][1] == loaded_platform

    event_integration = await loader.async_get_integration(hass, "event")
    with (
        patch.object(event_integration, "async_get_platforms", side_effect=ImportError),
        patch.object(event_integration, "get_platform_cached", return_value=None),
    ):
        hass.bus.async_fire(EVENT_COMPONENT_LOADED, {ATTR_COMPONENT: "event"})
        await hass.async_block_till_done()

    assert len(processed) == 1
    assert "Unexpected error importing integration platforms for event" in caplog.text


@callback
def _process_platform_callback(
    hass: HomeAssistant, domain: str, platform: ModuleType
) -> None:
    """Process platform."""
    raise HomeAssistantError("Non-compliant platform")


async def _process_platform_coro(
    hass: HomeAssistant, domain: str, platform: ModuleType
) -> None:
    """Process platform."""
    raise HomeAssistantError("Non-compliant platform")


@pytest.mark.no_fail_on_log_exception
@pytest.mark.parametrize(
    "process_platform", [_process_platform_callback, _process_platform_coro]
)
async def test_process_integration_platforms_non_compliant(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, process_platform: Callable
) -> None:
    """Test processing integrations using with a non-compliant platform."""
    loaded_platform = Mock()
    mock_platform(hass, "loaded_unique_880.platform_to_check", loaded_platform)
    hass.config.components.add("loaded_unique_880")

    event_platform = Mock()
    mock_platform(hass, "event_unique_990.platform_to_check", event_platform)

    processed = []

    await async_process_integration_platforms(
        hass, "platform_to_check", process_platform
    )
    await hass.async_block_till_done()

    assert len(processed) == 0
    assert "Exception in " in caplog.text
    assert "platform_to_check" in caplog.text
    assert "Non-compliant platform" in caplog.text
    assert "loaded_unique_880" in caplog.text
    caplog.clear()

    hass.bus.async_fire(EVENT_COMPONENT_LOADED, {ATTR_COMPONENT: "event_unique_990"})
    await hass.async_block_till_done()

    assert "Exception in " in caplog.text
    assert "platform_to_check" in caplog.text
    assert "Non-compliant platform" in caplog.text
    assert "event_unique_990" in caplog.text

    assert len(processed) == 0


async def test_broken_integration(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test handling an integration with a broken or missing manifest."""
    Mock()
    hass.config.components.add("loaded")

    event_platform = Mock()
    mock_platform(hass, "event.platform_to_check", event_platform)

    processed = []

    async def _process_platform(
        hass: HomeAssistant, domain: str, platform: Any
    ) -> None:
        """Process platform."""
        processed.append((domain, platform))

    await async_process_integration_platforms(
        hass, "platform_to_check", _process_platform
    )
    await hass.async_block_till_done()

    # This should never actually happen as the component cannot be
    # in hass.config.components without a loaded manifest
    assert len(processed) == 0


async def test_process_integration_platforms_no_integrations(
    hass: HomeAssistant,
) -> None:
    """Test processing integrations when no integrations are loaded."""
    event_platform = Mock()
    mock_platform(hass, "event.platform_to_check", event_platform)

    processed = []

    async def _process_platform(
        hass: HomeAssistant, domain: str, platform: Any
    ) -> None:
        """Process platform."""
        processed.append((domain, platform))

    await async_process_integration_platforms(
        hass, "platform_to_check", _process_platform
    )
    await hass.async_block_till_done()

    assert len(processed) == 0


async def test_lazy_integration_platforms(hass: HomeAssistant) -> None:
    """Test lazily loading and processing an integration platform on demand."""
    loaded_platform = Mock()
    mock_platform(hass, "loaded.platform_to_check", loaded_platform)
    hass.config.components.add("loaded")

    processed: list[str] = []

    @callback
    def _process_platform(hass: HomeAssistant, domain: str, platform: Any) -> Any:
        processed.append(domain)
        return platform

    platforms = LazyIntegrationPlatforms(hass, "platform_to_check", _process_platform)

    # Nothing is processed until the platform is requested.
    assert processed == []

    assert await platforms.async_get_platform("loaded") is loaded_platform
    assert processed == ["loaded"]

    # Subsequent requests are served from the cache without reprocessing.
    assert await platforms.async_get_platform("loaded") is loaded_platform
    assert processed == ["loaded"]


async def test_lazy_integration_platforms_not_loaded(hass: HomeAssistant) -> None:
    """Test the platform is not processed for an integration that is not loaded."""

    @callback
    def _process_platform(hass: HomeAssistant, domain: str, platform: Any) -> Any:
        return platform

    platforms = LazyIntegrationPlatforms(hass, "platform_to_check", _process_platform)

    loaded_platform = Mock()
    mock_platform(hass, "not_loaded.platform_to_check", loaded_platform)

    # The component is not loaded yet, so it is not processed or cached.
    assert await platforms.async_get_platform("not_loaded") is None

    # Once the component is loaded, the platform is served.
    hass.config.components.add("not_loaded")
    assert await platforms.async_get_platform("not_loaded") is loaded_platform


async def test_lazy_integration_platforms_no_platform(hass: HomeAssistant) -> None:
    """Test a loaded integration without the platform returns None."""
    mock_integration(hass, MockModule("loaded"))
    hass.config.components.add("loaded")

    processed: list[str] = []

    @callback
    def _process_platform(hass: HomeAssistant, domain: str, platform: Any) -> Any:
        processed.append(domain)
        return platform

    platforms = LazyIntegrationPlatforms(hass, "platform_to_check", _process_platform)

    assert await platforms.async_get_platform("loaded") is None
    # The platform does not exist, so the process callback is never called.
    assert processed == []


async def test_lazy_integration_platforms_get_platforms(hass: HomeAssistant) -> None:
    """Test enumerating all loaded integrations that provide the platform."""
    platform_a = Mock()
    mock_platform(hass, "integration_a.platform_to_check", platform_a)
    hass.config.components.add("integration_a")

    platform_b = Mock()
    mock_platform(hass, "integration_b.platform_to_check", platform_b)
    hass.config.components.add("integration_b")

    # A loaded integration without the platform is omitted.
    mock_integration(hass, MockModule("integration_c"))
    hass.config.components.add("integration_c")

    processed: list[str] = []

    @callback
    def _process_platform(hass: HomeAssistant, domain: str, platform: Any) -> Any:
        processed.append(domain)
        return platform

    platforms = LazyIntegrationPlatforms(hass, "platform_to_check", _process_platform)

    expected = {"integration_a": platform_a, "integration_b": platform_b}
    assert await platforms.async_get_platforms() == expected
    assert sorted(processed) == ["integration_a", "integration_b"]

    # A second call is served entirely from the cache without reprocessing.
    assert await platforms.async_get_platforms() == expected
    assert sorted(processed) == ["integration_a", "integration_b"]


async def test_lazy_integration_platforms_import_fails(hass: HomeAssistant) -> None:
    """Test a platform that fails to import is cached as None."""
    mock_platform(hass, "loaded.platform_to_check", Mock())
    hass.config.components.add("loaded")

    processed: list[str] = []

    @callback
    def _process_platform(hass: HomeAssistant, domain: str, platform: Any) -> Any:
        processed.append(domain)
        return platform

    platforms = LazyIntegrationPlatforms(hass, "platform_to_check", _process_platform)

    integration = await loader.async_get_integration(hass, "loaded")
    with patch.object(integration, "async_get_platform", side_effect=ImportError):
        assert await platforms.async_get_platform("loaded") is None

    # The process callback was never called and the failure is cached, so a
    # subsequent request does not retry the import.
    assert processed == []
    assert await platforms.async_get_platform("loaded") is None


async def test_lazy_integration_platforms_process_raises(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a process callback that raises is isolated to its integration."""
    good_platform = Mock()
    mock_platform(hass, "good.platform_to_check", good_platform)
    hass.config.components.add("good")
    mock_platform(hass, "bad.platform_to_check", Mock())
    hass.config.components.add("bad")

    @callback
    def _process_platform(hass: HomeAssistant, domain: str, platform: Any) -> Any:
        if domain == "bad":
            raise ValueError("boom")
        return platform

    platforms = LazyIntegrationPlatforms(hass, "platform_to_check", _process_platform)

    # The failing integration is skipped; the others are still returned.
    assert await platforms.async_get_platforms() == {"good": good_platform}
    assert "Error processing platform_to_check platform for bad" in caplog.text


async def test_lazy_integration_platforms_concurrent(hass: HomeAssistant) -> None:
    """Test concurrent requests for the same domain process it only once."""
    loaded_platform = Mock()
    mock_platform(hass, "loaded.platform_to_check", loaded_platform)
    hass.config.components.add("loaded")

    processed: list[str] = []

    @callback
    def _process_platform(hass: HomeAssistant, domain: str, platform: Any) -> Any:
        processed.append(domain)
        return platform

    platforms = LazyIntegrationPlatforms(hass, "platform_to_check", _process_platform)

    # Block the import so both callers are in flight at the same time.
    integration = await loader.async_get_integration(hass, "loaded")
    event = asyncio.Event()

    async def _blocking_get_platform(platform_name: str) -> Any:
        await event.wait()
        return loaded_platform

    with patch.object(
        integration, "async_get_platform", side_effect=_blocking_get_platform
    ):
        first = asyncio.ensure_future(platforms.async_get_platform("loaded"))
        second = asyncio.ensure_future(platforms.async_get_platform("loaded"))
        await asyncio.sleep(0)
        event.set()
        results = await asyncio.gather(first, second)

    assert results == [loaded_platform, loaded_platform]
    # The platform was imported and processed exactly once.
    assert processed == ["loaded"]
