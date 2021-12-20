"""Test the service platform helper."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady
from homeassistant.helpers.service_integration import ServiceIntegration
from homeassistant.helpers.service_platform import (
    SLOW_SETUP_WARNING,
    AddServicesCallback,
    PlatformService,
    ServiceDescription,
    ServicePlatform,
    async_get_platforms,
)
from homeassistant.util.dt import utcnow

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    MockPlatformService,
    async_fire_time_changed,
    mock_integration,
    mock_platform as mock_platform_helper,
)

_LOGGER = logging.getLogger(__name__)
DOMAIN = "test_domain"
ENTRY_DOMAIN = "entry_domain"
HELLO_SERVICE_YAML = {
    "hello": {
        "name": "Say hello",
        "description": "This service says hello.",
        "fields": {},
    }
}
GOODBYE_SERVICE_YAML = {
    "goodbye": {
        "name": "Say goodbye",
        "description": "This service says goodbye.",
        "fields": {},
    }
}
MOCK_SERVICES_YAML = {
    "mock": {
        "name": "Mock a service",
        "description": "This service mocks a service.",
        "fields": {},
    }
}
PLATFORM = "test_platform"
ORIGINAL_EXCEPTION = HomeAssistantError("The device dropped the connection")
PLATFORM_EXCEPTION = PlatformNotReady()
PLATFORM_EXCEPTION.__cause__ = ORIGINAL_EXCEPTION


@pytest.fixture(name="mock_service_integration")
async def mock_service_integration_fixture(
    hass, mock_platform: tuple[MockPlatform, AsyncMock, ConfigEntry]
) -> ServiceIntegration:
    """Mock a service integration."""
    test_domain_integration = mock_integration(hass, MockModule(DOMAIN))
    test_domain_integration.file_path = Path("mock_path")
    service_integration = ServiceIntegration(hass, _LOGGER, DOMAIN, {DOMAIN: None})
    return service_integration


@pytest.fixture(name="mock_service_platform")
async def mock_service_platform_fixture(
    hass: HomeAssistant,
    mock_platform: tuple[MockPlatform, AsyncMock, ConfigEntry],
    mock_service_integration: ServiceIntegration,
) -> ServicePlatform:
    """Mock a service platform."""
    platform, _, entry = mock_platform
    service_platform = ServicePlatform(
        hass=hass,
        logger=_LOGGER,
        domain=DOMAIN,
        platform_name=entry.domain,
        platform=platform,
    )
    return service_platform


@pytest.fixture(name="mock_platform")
async def mock_platform_fixture(
    hass: HomeAssistant,
) -> tuple[MockPlatform, AsyncMock, ConfigEntry]:
    """Mock a service platform module."""
    mock_integration(hass, MockModule(ENTRY_DOMAIN))
    mock_setup_entry = AsyncMock()
    platform = mock_platform_helper(
        hass,
        f"{ENTRY_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=mock_setup_entry),
    )
    entry = MockConfigEntry(domain=ENTRY_DOMAIN)
    return platform, mock_setup_entry, entry


@pytest.fixture(name="mock_platform_service")
def mock_platform_service_fixture() -> PlatformService:
    """Mock a platform service."""
    return MockPlatformService(
        service_name="test_service_mock",
        service_description=ServiceDescription(
            "mock",
            "test_service_mock",
            "Test a service",
            "Description for testing a service",
        ),
        service_schema=vol.Schema({}),
    )


@pytest.fixture(autouse=True)
async def mock_load_services_yaml(hass):
    """Mock services yaml descriptions."""
    with patch(
        "homeassistant.helpers.service.load_yaml", return_value=MOCK_SERVICES_YAML
    ) as load_yaml:
        yield load_yaml


async def test_platform_warn_slow_setup(
    hass: HomeAssistant,
    mock_platform: tuple[MockPlatform, AsyncMock, ConfigEntry],
    mock_service_integration: ServiceIntegration,
) -> None:
    """Warn we log when platform setup takes a long time."""
    entry = mock_platform[2]

    with patch.object(hass.loop, "call_later") as mock_call:
        await mock_service_integration.async_setup()
        assert await mock_service_integration.async_setup_entry(entry)
        await hass.async_block_till_done()
        assert mock_call.called

        # mock_calls[0] is the warning message for integration setup
        # mock_calls[3] is the warning message for platform setup
        timeout, logger_method = mock_call.mock_calls[3][1][:2]

        assert timeout == SLOW_SETUP_WARNING
        assert logger_method == _LOGGER.warning
        assert mock_call().cancel.called


async def test_platform_error_slow_setup(
    hass: HomeAssistant,
    mock_platform: tuple[MockPlatform, AsyncMock, ConfigEntry],
    mock_service_integration: ServiceIntegration,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Don't block startup more than SLOW_SETUP_MAX_WAIT."""
    platform, _, entry = mock_platform
    called = []

    async def mock_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_services: AddServicesCallback,
    ) -> None:
        called.append(1)
        await asyncio.sleep(1)

    platform.async_setup_entry = mock_setup_entry

    with patch("homeassistant.helpers.service_platform.SLOW_SETUP_MAX_WAIT", 0):
        await mock_service_integration.async_setup()
        assert not await mock_service_integration.async_setup_entry(entry)
        await hass.async_block_till_done()

    assert len(called) == 1
    assert f"{DOMAIN}.{ENTRY_DOMAIN}" not in hass.config.components
    assert (
        f"Setup of platform {ENTRY_DOMAIN} is taking longer than 0 seconds"
        in caplog.text
    )


@pytest.mark.parametrize(
    "parallel_updates_constant, parallel_updates",
    [(None, asyncio.Semaphore(1)), (0, None), (2, asyncio.Semaphore(2))],
)
async def test_parallel_updates(
    hass: HomeAssistant,
    mock_platform: tuple[MockPlatform, AsyncMock, ConfigEntry],
    mock_service_integration: ServiceIntegration,
    mock_platform_service: PlatformService,
    parallel_updates_constant: int | None,
    parallel_updates: asyncio.Semaphore | None,
) -> None:
    """Test platform parallel_updates limit."""
    platform, mock_setup_entry, entry = mock_platform
    platform.PARALLEL_UPDATES = parallel_updates_constant  # type: ignore[attr-defined]

    await mock_service_integration.async_setup()
    assert await mock_service_integration.async_setup_entry(entry)
    await hass.async_block_till_done()

    async_add_services = mock_setup_entry.mock_calls[0][1][2]
    with patch(
        "homeassistant.helpers.service.load_yaml", return_value=MOCK_SERVICES_YAML
    ):
        async_add_services([mock_platform_service])
        await hass.async_block_till_done()

    platform_services = list(mock_service_integration.services)
    assert platform_services

    platform_service = platform_services[0]
    # pylint: disable=unidiomatic-typecheck
    assert type(platform_service.parallel_updates) == type(parallel_updates)
    assert getattr(platform_service.parallel_updates, "_value", None) == getattr(
        parallel_updates, "_value", None
    )


async def test_setup_entry_and_reset(
    hass: HomeAssistant,
    mock_platform: tuple[MockPlatform, AsyncMock, ConfigEntry],
    mock_service_platform: ServicePlatform,
    mock_platform_service: PlatformService,
) -> None:
    """Test we can set up an entry and destroy the platform."""
    platform, _, entry = mock_platform
    full_platform_name = f"{mock_service_platform.domain}.{entry.domain}"

    async def mock_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_services: AddServicesCallback,
    ) -> None:
        """Mock setup entry method."""
        async_add_services([mock_platform_service])

    platform.async_setup_entry = mock_setup_entry

    assert full_platform_name not in hass.config.components
    assert len(hass.services.async_services()) == 0

    assert await mock_service_platform.async_setup_entry(entry)
    await hass.async_block_till_done()

    assert full_platform_name in hass.config.components
    assert len(hass.services.async_services()) == 1
    assert hass.services.has_service(
        mock_service_platform.domain, mock_platform_service.service_name
    )
    assert mock_service_platform.config_entry is entry

    mock_service_platform.async_destroy()

    assert len(hass.services.async_services()) == 0


@pytest.mark.parametrize(
    "error, log_text, call_later_calls",
    [
        (PlatformNotReady(), "Platform entry_domain not ready yet", 1),
        (
            PlatformNotReady("lp0 on fire"),
            "Platform entry_domain not ready yet: lp0 on fire",
            1,
        ),
        (
            PLATFORM_EXCEPTION,
            "Platform entry_domain not ready yet: The device dropped the connection",
            1,
        ),
        (
            Exception("Boom"),
            f"Error while setting up {ENTRY_DOMAIN} platform for {DOMAIN}",
            0,
        ),
    ],
)
async def test_setup_entry_platform_error(
    hass: HomeAssistant,
    mock_platform: tuple[MockPlatform, AsyncMock, ConfigEntry],
    mock_service_platform: ServicePlatform,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
    log_text: str,
    call_later_calls: int,
) -> None:
    """Test when an entry has an error during platform setup."""
    platform, _, entry = mock_platform
    mock_setup_entry = AsyncMock(side_effect=error)
    platform.async_setup_entry = mock_setup_entry

    with patch(
        "homeassistant.helpers.service_platform.async_call_later"
    ) as mock_call_later:
        assert not await mock_service_platform.async_setup_entry(entry)

    full_name = f"{mock_service_platform.domain}.{entry.domain}"
    assert full_name not in hass.config.components
    assert len(mock_setup_entry.mock_calls) == 1
    assert log_text in caplog.text
    assert len(mock_call_later.mock_calls) == call_later_calls


async def test_setup_entry_platform_try_again(
    hass: HomeAssistant,
    mock_platform: tuple[MockPlatform, AsyncMock, ConfigEntry],
    mock_service_platform: ServicePlatform,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test when an entry wants to try again to setup platform."""
    platform, _, entry = mock_platform
    mock_setup_entry = AsyncMock(side_effect=PlatformNotReady("Too slow"))
    platform.async_setup_entry = mock_setup_entry

    assert not await mock_service_platform.async_setup_entry(entry)

    full_name = f"{mock_service_platform.domain}.{entry.domain}"
    assert full_name not in hass.config.components
    assert len(mock_setup_entry.mock_calls) == 1
    log_message = (
        f"Platform {ENTRY_DOMAIN} not ready yet: Too slow; "
        "Retrying in background in 30 seconds"
    )
    assert (__name__, logging.WARNING, log_message) in caplog.record_tuples

    caplog.clear()
    retry_time = utcnow() + timedelta(seconds=30)
    async_fire_time_changed(hass, retry_time)
    await hass.async_block_till_done()

    assert full_name not in hass.config.components
    assert len(mock_setup_entry.mock_calls) == 2
    log_message = (
        f"Platform {ENTRY_DOMAIN} not ready yet: Too slow; Retrying in 60 seconds"
    )
    assert (__name__, logging.DEBUG, log_message) in caplog.record_tuples


@pytest.mark.parametrize("platform_call", ["async_destroy", "async_shutdown"])
@pytest.mark.parametrize(
    "core_state, call_later_calls, retry_listeners",
    [(CoreState.running, 1, 0), (CoreState.starting, 0, 1)],
)
async def test_platform_cancels_retry_setup(
    hass: HomeAssistant,
    mock_platform: tuple[MockPlatform, AsyncMock, ConfigEntry],
    mock_service_platform: ServicePlatform,
    core_state: CoreState,
    call_later_calls: int,
    retry_listeners: int,
    platform_call: str,
) -> None:
    """Test resetting or shutting down a platform will cancel setup retry."""
    # pylint: disable=protected-access
    hass.state = core_state
    initial_listeners = hass.bus.async_listeners()[EVENT_HOMEASSISTANT_STARTED]
    platform, _, entry = mock_platform
    mock_setup_entry = AsyncMock(side_effect=PlatformNotReady())
    platform.async_setup_entry = mock_setup_entry

    with patch(
        "homeassistant.helpers.service_platform.async_call_later"
    ) as mock_call_later:
        assert not await mock_service_platform.async_setup_entry(entry)
        await hass.async_block_till_done()

    assert len(mock_call_later.mock_calls) == call_later_calls
    assert len(mock_call_later.return_value.mock_calls) == 0
    assert (
        hass.bus.async_listeners()[EVENT_HOMEASSISTANT_STARTED]
        == initial_listeners + retry_listeners
    )
    assert mock_service_platform._async_cancel_retry_setup is not None

    getattr(mock_service_platform, platform_call)()
    await hass.async_block_till_done()

    assert len(mock_call_later.return_value.mock_calls) == call_later_calls
    assert hass.bus.async_listeners()[EVENT_HOMEASSISTANT_STARTED] == initial_listeners
    assert mock_service_platform._async_cancel_retry_setup is None


async def test_remove_service(
    hass: HomeAssistant,
    mock_platform: tuple[MockPlatform, AsyncMock, ConfigEntry],
    mock_service_integration: ServiceIntegration,
    mock_platform_service: PlatformService,
) -> None:
    """Remove a service from a platform."""
    _, mock_setup_entry, entry = mock_platform

    await mock_service_integration.async_setup()
    assert await mock_service_integration.async_setup_entry(entry)
    await hass.async_block_till_done()

    async_add_services = mock_setup_entry.mock_calls[0][1][2]

    with patch(
        "homeassistant.helpers.service.load_yaml", return_value=MOCK_SERVICES_YAML
    ):
        async_add_services([mock_platform_service])
        await hass.async_block_till_done()

    assert len(hass.services.async_services()) == 1
    mock_platform_service.async_remove()
    assert len(hass.services.async_services()) == 0


async def test_adding_empty_services(
    hass: HomeAssistant,
    mock_platform: tuple[MockPlatform, AsyncMock, ConfigEntry],
    mock_service_integration: ServiceIntegration,
) -> None:
    """Test not failing when getting empty services list."""
    _, mock_setup_entry, entry = mock_platform

    await mock_service_integration.async_setup()
    assert await mock_service_integration.async_setup_entry(entry)
    await hass.async_block_till_done()

    async_add_services = mock_setup_entry.mock_calls[0][1][2]

    with patch(
        "homeassistant.helpers.service.load_yaml", return_value=MOCK_SERVICES_YAML
    ):
        async_add_services([])
        await hass.async_block_till_done()

    assert len(hass.services.async_services()) == 0


async def test_adding_removing_same_service_twice(
    hass: HomeAssistant,
    mock_platform: tuple[MockPlatform, AsyncMock, ConfigEntry],
    mock_service_platform: ServicePlatform,
    mock_platform_service: PlatformService,
) -> None:
    """Test adding the same service twice."""
    # Test adding the same service twice at the same time.
    with patch(
        "homeassistant.helpers.service.load_yaml", return_value=MOCK_SERVICES_YAML
    ), pytest.raises(HomeAssistantError):
        await mock_service_platform.async_add_services(
            [mock_platform_service, mock_platform_service]
        )

    # Flush out remaining running service registration.
    await hass.async_block_till_done()
    assert len(hass.services.async_services()) == 1

    for service in list(mock_service_platform.services.values()):
        service.async_remove()

    assert len(hass.services.async_services()) == 0

    # Test adding the same service in two different calls.
    with patch(
        "homeassistant.helpers.service.load_yaml", return_value=MOCK_SERVICES_YAML
    ):
        await mock_service_platform.async_add_services([mock_platform_service])

    assert len(hass.services.async_services()) == 1
    assert hass.services.has_service(DOMAIN, mock_platform_service.service_name)

    with patch(
        "homeassistant.helpers.service.load_yaml", return_value=MOCK_SERVICES_YAML
    ), pytest.raises(HomeAssistantError):
        await mock_service_platform.async_add_services([mock_platform_service])

    assert len(hass.services.async_services()) == 1
    assert hass.services.has_service(DOMAIN, mock_platform_service.service_name)

    for service in list(mock_service_platform.services.values()):
        service.async_remove()

    assert len(hass.services.async_services()) == 0

    # Test removing the same service again.
    with pytest.raises(HomeAssistantError):
        mock_platform_service.async_remove()


async def test_timeout_when_adding_service(
    hass: HomeAssistant,
    mock_platform: tuple[MockPlatform, AsyncMock, ConfigEntry],
    mock_service_platform: ServicePlatform,
    mock_platform_service: PlatformService,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test timeout when adding a service."""

    async def slow_get_integration(*args):
        await asyncio.sleep(1)

    with patch(
        "homeassistant.helpers.service_platform.async_get_integration",
        side_effect=slow_get_integration,
    ), patch(
        "homeassistant.helpers.service_platform.SLOW_ADD_SERVICE_MAX_WAIT", new=0
    ), patch(
        "homeassistant.helpers.service_platform.SLOW_ADD_MIN_TIMEOUT", new=0
    ):
        await mock_service_platform.async_add_services([mock_platform_service])

    assert len(hass.services.async_services()) == 0
    assert (
        f"Timed out adding service for domain {mock_service_platform.domain} "
        f"with platform {mock_service_platform.platform_name}" in caplog.text
    )


async def test_error_when_adding_service(
    hass: HomeAssistant,
    mock_platform: tuple[MockPlatform, AsyncMock, ConfigEntry],
    mock_service_platform: ServicePlatform,
    mock_platform_service: PlatformService,
) -> None:
    """Test error when adding a service."""
    with patch(
        "homeassistant.helpers.service.load_yaml", side_effect=HomeAssistantError()
    ), pytest.raises(HomeAssistantError):
        await mock_service_platform.async_add_services([mock_platform_service])

    assert len(hass.services.async_services()) == 0

    # Test that we can add the same service if the error is resolved.

    with patch(
        "homeassistant.helpers.service.load_yaml", return_value=MOCK_SERVICES_YAML
    ):
        await mock_service_platform.async_add_services([mock_platform_service])

    assert len(hass.services.async_services()) == 1
    assert hass.services.has_service(DOMAIN, mock_platform_service.service_name)


async def test_platforms_sharing_services(
    hass: HomeAssistant,
    mock_platform: tuple[MockPlatform, AsyncMock, ConfigEntry],
    mock_service_integration: ServiceIntegration,
) -> None:
    """Test platforms share services."""
    # Add three platforms and three services for the same config entry
    # where two platforms share the same domain and the same service name.
    different_domain = "different_integration"
    platform, _, entry = mock_platform
    service_platform_1 = ServicePlatform(
        hass=hass,
        logger=_LOGGER,
        domain=DOMAIN,
        platform_name=entry.domain,
        platform=platform,
    )
    service_1 = MockPlatformService(
        service_name="test_hello",
        service_description=ServiceDescription(
            "hello",
            "test_hello",
            "Test saying hello",
            "Description for hello",
        ),
        service_schema=vol.Schema({}),
    )
    service_1.async_handle_service = AsyncMock()  # type: ignore[assignment]
    service_platform_2 = ServicePlatform(
        hass=hass,
        logger=_LOGGER,
        domain=DOMAIN,
        platform_name=entry.domain,
        platform=platform,
    )
    service_2 = MockPlatformService(
        service_name="test_hello",
        service_description=ServiceDescription(
            "hello",
            "test_hello",
            "Test saying hello",
            "Description for hello",
        ),
        service_schema=vol.Schema({}),
    )
    service_2.async_handle_service = AsyncMock()  # type: ignore[assignment]
    service_platform_3 = ServicePlatform(
        hass=hass,
        logger=_LOGGER,
        domain=different_domain,
        platform_name=entry.domain,
        platform=platform,
    )
    service_3 = MockPlatformService(
        service_name="test_goodbye",
        service_description=ServiceDescription(
            "goodbye",
            "test_goodbye",
            "Test saying goodbye",
            "Description for goodbye",
        ),
        service_schema=vol.Schema({}),
    )
    service_3.async_handle_service = AsyncMock()  # type: ignore[assignment]

    different_domain_integration = mock_integration(hass, MockModule(different_domain))
    different_domain_integration.file_path = Path("mock_different_path")
    different_service_integration = ServiceIntegration(
        hass, _LOGGER, different_domain, {different_domain: None}
    )
    platform = mock_platform_helper(
        hass,
        f"{ENTRY_DOMAIN}.{different_domain}",
        MockPlatform(async_setup_entry=AsyncMock()),
    )
    await mock_service_integration.async_setup()
    assert await mock_service_integration.async_setup_entry(entry)
    await different_service_integration.async_setup()
    assert await different_service_integration.async_setup_entry(entry)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.helpers.service.load_yaml",
        side_effect=[HELLO_SERVICE_YAML, GOODBYE_SERVICE_YAML],
    ):
        await service_platform_1.async_add_services([service_1])
        await service_platform_2.async_add_services([service_2])
        await service_platform_3.async_add_services([service_3])

    await hass.services.async_call(DOMAIN, "test_hello", blocking=True)

    # Both services of platform 1 and 2 should be called,
    # but not the service of platform 3.
    assert service_1.async_handle_service.call_count == 1
    assert service_2.async_handle_service.call_count == 1
    assert service_3.async_handle_service.call_count == 0

    await hass.services.async_call(different_domain, "test_goodbye", blocking=True)

    # Service 3 should be called,
    # but the calls of services of platform 1 and 2 are still at 1 each.
    assert service_1.async_handle_service.call_count == 1
    assert service_2.async_handle_service.call_count == 1
    assert service_3.async_handle_service.call_count == 1

    service_1.async_remove()

    # The test_hello service is still registered with the core
    # since service 2 is not removed.
    assert hass.services.has_service(DOMAIN, "test_hello")
    assert hass.services.has_service(different_domain, "test_goodbye")

    service_2.async_remove()

    # The test_hello service is not registered with the core anymore
    # since service 2 is now also removed.
    assert not hass.services.has_service(DOMAIN, "test_hello")
    assert hass.services.has_service(different_domain, "test_goodbye")


async def test_get_platforms(
    hass: HomeAssistant,
    mock_platform: tuple[MockPlatform, AsyncMock, ConfigEntry],
    mock_service_integration: ServiceIntegration,
) -> None:
    """Test get platforms with helper function."""
    platform, _, entry = mock_platform

    platforms = async_get_platforms(hass, ENTRY_DOMAIN)

    assert len(platforms) == 0

    service_platform = ServicePlatform(
        hass=hass,
        logger=_LOGGER,
        domain=DOMAIN,
        platform_name=entry.domain,
        platform=platform,
    )

    platforms = async_get_platforms(hass, ENTRY_DOMAIN)

    assert len(platforms) == 1
    assert platforms[0] is service_platform

    service_platform.async_destroy()
    platforms = async_get_platforms(hass, ENTRY_DOMAIN)

    assert not platforms

    with pytest.raises(ValueError):
        service_platform.async_destroy()
