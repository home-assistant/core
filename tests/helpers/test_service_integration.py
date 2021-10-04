"""Test the service integration helper."""
import logging
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.service_integration import ServiceIntegration
from homeassistant.helpers.service_platform import (
    ServiceDescription,
    async_get_platforms,
)

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    MockPlatformService,
    mock_integration,
    mock_platform,
)

_LOGGER = logging.getLogger(__name__)
DOMAIN = "test_domain"
ENTRY_DOMAIN = "entry_domain"
MOCK_SERVICES_YAML = {
    "mock": {
        "name": "Mock a service",
        "description": "This service mocks a service.",
        "fields": {},
    }
}


async def test_platforms_shutdown_on_stop(hass):
    """Test that we shutdown platforms on stop."""
    mock_setup_entry = AsyncMock()
    mock_integration(hass, MockModule(ENTRY_DOMAIN))
    mock_platform(
        hass,
        f"{ENTRY_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=mock_setup_entry),
    )
    entry = MockConfigEntry(domain=ENTRY_DOMAIN)
    service_integration = ServiceIntegration(hass, _LOGGER, DOMAIN, {DOMAIN: None})

    await service_integration.async_setup()
    assert await service_integration.async_setup_entry(entry)
    await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 1
    p_hass, p_entry, _ = mock_setup_entry.mock_calls[0][1]
    assert p_hass is hass
    assert p_entry is entry
    assert f"{DOMAIN}.{ENTRY_DOMAIN}" in hass.config.components

    platforms = async_get_platforms(hass, ENTRY_DOMAIN)

    assert platforms

    test_platform = platforms[0]

    with patch.object(test_platform, "async_shutdown") as mock_async_shutdown:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    assert mock_async_shutdown.called


async def test_setup_dependencies_platform(hass):
    """Test we setup the dependencies of a platform.

    We're explicitly testing that we process dependencies even if a component
    with the same name has already been loaded.
    """
    mock_setup_entry = AsyncMock()
    mock_integration(
        hass, MockModule("test_integration", dependencies=["test_integration2"])
    )
    mock_integration(hass, MockModule("test_integration2"))
    mock_platform(
        hass,
        "test_integration.test_domain",
        MockPlatform(async_setup_entry=mock_setup_entry),
    )
    entry = MockConfigEntry(domain="test_integration")
    service_integration = ServiceIntegration(hass, _LOGGER, DOMAIN, {DOMAIN: None})

    await service_integration.async_setup()
    assert await service_integration.async_setup_entry(entry)
    await hass.async_block_till_done()

    assert "test_integration" in hass.config.components
    assert "test_integration2" in hass.config.components
    assert "test_domain.test_integration" in hass.config.components


async def test_setup_entry(hass):
    """Test setup entry calls async_setup_entry on platform."""
    mock_integration(hass, MockModule(ENTRY_DOMAIN))
    mock_setup_entry = AsyncMock()
    mock_platform(
        hass,
        f"{ENTRY_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=mock_setup_entry),
    )
    entry = MockConfigEntry(domain=ENTRY_DOMAIN)
    service_integration = ServiceIntegration(hass, _LOGGER, DOMAIN, {DOMAIN: None})

    assert await service_integration.async_setup_entry(entry)
    assert len(mock_setup_entry.mock_calls) == 1
    p_hass, p_entry, _ = mock_setup_entry.mock_calls[0][1]
    assert p_hass is hass
    assert p_entry is entry


async def test_setup_entry_platform_not_exist(hass):
    """Test setup entry fails if platform does not exist."""
    entry = MockConfigEntry(domain="non_existing")
    service_integration = ServiceIntegration(hass, _LOGGER, DOMAIN, {DOMAIN: None})

    assert (await service_integration.async_setup_entry(entry)) is False


async def test_setup_entry_fails_duplicate(hass):
    """Test we don't allow setting up a config entry twice."""
    mock_integration(hass, MockModule(ENTRY_DOMAIN))
    mock_setup_entry = AsyncMock()
    mock_platform(
        hass,
        f"{ENTRY_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=mock_setup_entry),
    )
    entry = MockConfigEntry(domain=ENTRY_DOMAIN)
    service_integration = ServiceIntegration(hass, _LOGGER, DOMAIN, {DOMAIN: None})

    assert await service_integration.async_setup_entry(entry)

    with pytest.raises(ValueError):
        await service_integration.async_setup_entry(entry)


async def test_unload_entry_resets_platform(hass):
    """Test unloading an entry removes all entities."""
    test_domain_integration = mock_integration(hass, MockModule(DOMAIN))
    test_domain_integration.file_path = Path("mock_path")
    mock_setup_entry = AsyncMock()
    mock_platform(
        hass,
        f"{ENTRY_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=mock_setup_entry),
    )
    entry = MockConfigEntry(domain=ENTRY_DOMAIN)
    service_integration = ServiceIntegration(hass, _LOGGER, DOMAIN, {DOMAIN: None})

    assert await service_integration.async_setup_entry(entry)

    assert len(mock_setup_entry.mock_calls) == 1

    async_add_services = mock_setup_entry.mock_calls[0][1][2]
    with patch(
        "homeassistant.helpers.service.load_yaml", return_value=MOCK_SERVICES_YAML
    ):
        async_add_services(
            [
                MockPlatformService(
                    service_name="test_service_mock",
                    service_description=ServiceDescription(
                        "mock",
                        "test_service_mock",
                        "Test a service",
                        "Description for testing a service",
                    ),
                    service_schema=vol.Schema({}),
                )
            ]
        )
        await hass.async_block_till_done()

    assert len(hass.services.async_services()) == 1
    assert len(list(service_integration.services)) == 1

    assert await service_integration.async_unload_entry(entry)

    assert len(hass.services.async_services()) == 0
    assert len(list(service_integration.services)) == 0


async def test_unload_entry_fails_if_never_loaded(hass):
    """Test unload entry fails if not loaded."""
    entry = MockConfigEntry(domain=ENTRY_DOMAIN)
    service_integration = ServiceIntegration(hass, _LOGGER, DOMAIN, {DOMAIN: None})

    with pytest.raises(ValueError):
        await service_integration.async_unload_entry(entry)
