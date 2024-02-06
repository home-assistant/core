"""Tests for the reload helper."""
import logging
from unittest.mock import AsyncMock, Mock, patch

import pytest
import voluptuous as vol

from homeassistant import config
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigValidationError, HomeAssistantError
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.reload import (
    async_get_platform_without_config_entry,
    async_integration_yaml_config,
    async_reload_integration_platforms,
    async_setup_reload_service,
)
from homeassistant.loader import async_get_integration

from tests.common import (
    MockModule,
    MockPlatform,
    get_fixture_path,
    mock_integration,
    mock_platform,
)

_LOGGER = logging.getLogger(__name__)
DOMAIN = "test_domain"
PLATFORM = "test_platform"


async def test_reload_platform(hass: HomeAssistant) -> None:
    """Test the polling of only updated entities."""
    component_setup = Mock(return_value=True)

    setup_called = []

    async def setup_platform(*args):
        setup_called.append(args)

    mock_integration(hass, MockModule(DOMAIN, setup=component_setup))
    mock_integration(hass, MockModule(PLATFORM, dependencies=[DOMAIN]))

    platform = MockPlatform(async_setup_platform=setup_platform)
    mock_platform(hass, f"{PLATFORM}.{DOMAIN}", platform)

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    await component.async_setup({DOMAIN: {"platform": PLATFORM, "sensors": None}})
    await hass.async_block_till_done()
    assert component_setup.called

    assert f"{PLATFORM}.{DOMAIN}" in hass.config.components
    assert len(setup_called) == 1

    platform = async_get_platform_without_config_entry(hass, PLATFORM, DOMAIN)
    assert platform.platform_name == PLATFORM
    assert platform.domain == DOMAIN

    yaml_path = get_fixture_path("helpers/reload_configuration.yaml")
    with patch.object(config, "YAML_CONFIG_FILE", yaml_path):
        await async_reload_integration_platforms(hass, PLATFORM, [DOMAIN])

    assert len(setup_called) == 2

    existing_platforms = async_get_platforms(hass, PLATFORM)
    for existing_platform in existing_platforms:
        existing_platform.config_entry = "abc"
    assert not async_get_platform_without_config_entry(hass, PLATFORM, DOMAIN)


async def test_setup_reload_service(hass: HomeAssistant) -> None:
    """Test setting up a reload service."""
    component_setup = Mock(return_value=True)

    setup_called = []

    async def setup_platform(*args):
        setup_called.append(args)

    mock_integration(hass, MockModule(DOMAIN, setup=component_setup))
    mock_integration(hass, MockModule(PLATFORM, dependencies=[DOMAIN]))

    platform = MockPlatform(async_setup_platform=setup_platform)
    mock_platform(hass, f"{PLATFORM}.{DOMAIN}", platform)

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    await component.async_setup({DOMAIN: {"platform": PLATFORM, "sensors": None}})
    await hass.async_block_till_done()
    assert component_setup.called

    assert f"{PLATFORM}.{DOMAIN}" in hass.config.components
    assert len(setup_called) == 1

    await async_setup_reload_service(hass, PLATFORM, [DOMAIN])

    yaml_path = get_fixture_path("helpers/reload_configuration.yaml")
    with patch.object(config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            PLATFORM,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(setup_called) == 2


async def test_setup_reload_service_when_async_process_component_config_fails(
    hass: HomeAssistant,
) -> None:
    """Test setting up a reload service with the config processing failing."""
    component_setup = Mock(return_value=True)

    setup_called = []

    async def setup_platform(*args):
        setup_called.append(args)

    mock_integration(hass, MockModule(DOMAIN, setup=component_setup))
    mock_integration(hass, MockModule(PLATFORM, dependencies=[DOMAIN]))

    platform = MockPlatform(async_setup_platform=setup_platform)
    mock_platform(hass, f"{PLATFORM}.{DOMAIN}", platform)

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    await component.async_setup({DOMAIN: {"platform": PLATFORM, "sensors": None}})
    await hass.async_block_till_done()
    assert component_setup.called

    assert f"{PLATFORM}.{DOMAIN}" in hass.config.components
    assert len(setup_called) == 1

    await async_setup_reload_service(hass, PLATFORM, [DOMAIN])

    yaml_path = get_fixture_path("helpers/reload_configuration.yaml")
    with patch.object(config, "YAML_CONFIG_FILE", yaml_path), patch.object(
        config,
        "async_process_component_config",
        return_value=config.IntegrationConfigInfo(None, []),
    ):
        await hass.services.async_call(
            PLATFORM,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(setup_called) == 1


async def test_setup_reload_service_with_platform_that_provides_async_reset_platform(
    hass: HomeAssistant,
) -> None:
    """Test setting up a reload service using a platform that has its own async_reset_platform."""
    component_setup = AsyncMock(return_value=True)

    setup_called = []
    async_reset_platform_called = []

    async def setup_platform(*args):
        setup_called.append(args)

    async def async_reset_platform(*args):
        async_reset_platform_called.append(args)

    mock_integration(hass, MockModule(DOMAIN, async_setup=component_setup))
    integration = await async_get_integration(hass, DOMAIN)
    integration.get_component().async_reset_platform = async_reset_platform

    mock_integration(hass, MockModule(PLATFORM, dependencies=[DOMAIN]))

    platform = MockPlatform(async_setup_platform=setup_platform)
    mock_platform(hass, f"{PLATFORM}.{DOMAIN}", platform)

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    await component.async_setup({DOMAIN: {"platform": PLATFORM, "name": "xyz"}})
    await hass.async_block_till_done()
    assert component_setup.called

    assert f"{PLATFORM}.{DOMAIN}" in hass.config.components
    assert len(setup_called) == 1

    await async_setup_reload_service(hass, PLATFORM, [DOMAIN])

    yaml_path = get_fixture_path("helpers/reload_configuration.yaml")
    with patch.object(config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            PLATFORM,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(setup_called) == 1
    assert len(async_reset_platform_called) == 1


async def test_async_integration_yaml_config(hass: HomeAssistant) -> None:
    """Test loading yaml config for an integration."""
    mock_integration(hass, MockModule(DOMAIN))

    yaml_path = get_fixture_path(f"helpers/{DOMAIN}_configuration.yaml")
    with patch.object(config, "YAML_CONFIG_FILE", yaml_path):
        processed_config = await async_integration_yaml_config(hass, DOMAIN)
        assert processed_config == {DOMAIN: [{"name": "one"}, {"name": "two"}]}
        # Test fetching yaml config does not raise when the raise_on_failure option is set
        processed_config = await async_integration_yaml_config(
            hass, DOMAIN, raise_on_failure=True
        )
        assert processed_config == {DOMAIN: [{"name": "one"}, {"name": "two"}]}


async def test_async_integration_failing_yaml_config(hass: HomeAssistant) -> None:
    """Test reloading yaml config for an integration fails.

    In case an integration reloads its yaml configuration it should throw when
    the new config failed to load and raise_on_failure is set to True.
    """
    schema_without_name_attr = vol.Schema({vol.Required("some_option"): str})

    mock_integration(hass, MockModule(DOMAIN, config_schema=schema_without_name_attr))

    yaml_path = get_fixture_path(f"helpers/{DOMAIN}_configuration.yaml")
    with patch.object(config, "YAML_CONFIG_FILE", yaml_path):
        # Test fetching yaml config does not raise without raise_on_failure option
        processed_config = await async_integration_yaml_config(hass, DOMAIN)
        assert processed_config is None
        # Test fetching yaml config does not raise when the raise_on_failure option is set
        with pytest.raises(ConfigValidationError):
            await async_integration_yaml_config(hass, DOMAIN, raise_on_failure=True)


async def test_async_integration_failing_on_reload(hass: HomeAssistant) -> None:
    """Test reloading yaml config for an integration fails with an other exception.

    In case an integration reloads its yaml configuration it should throw when
    the new config failed to load and raise_on_failure is set to True.
    """
    mock_integration(hass, MockModule(DOMAIN))

    yaml_path = get_fixture_path(f"helpers/{DOMAIN}_configuration.yaml")
    with patch.object(config, "YAML_CONFIG_FILE", yaml_path), patch(
        "homeassistant.config.async_process_component_config",
        side_effect=HomeAssistantError(),
    ), pytest.raises(HomeAssistantError):
        # Test fetching yaml config does raise when the raise_on_failure option is set
        await async_integration_yaml_config(hass, DOMAIN, raise_on_failure=True)


async def test_async_integration_missing_yaml_config(hass: HomeAssistant) -> None:
    """Test loading missing yaml config for an integration."""
    mock_integration(hass, MockModule(DOMAIN))

    yaml_path = get_fixture_path("helpers/does_not_exist_configuration.yaml")
    with pytest.raises(FileNotFoundError), patch.object(
        config, "YAML_CONFIG_FILE", yaml_path
    ):
        await async_integration_yaml_config(hass, DOMAIN)
