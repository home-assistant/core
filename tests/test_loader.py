"""Test to verify that we can load components."""
import pytest

import homeassistant.loader as loader
from homeassistant.components import http, hue
from homeassistant.components.hue import light as hue_light

from tests.common import MockModule, async_mock_service, mock_integration


def test_set_component(hass):
    """Test if set_component works."""
    comp = object()
    loader.set_component(hass, 'switch.test_set', comp)

    assert loader.get_component(hass, 'switch.test_set') is comp


def test_get_component(hass):
    """Test if get_component works."""
    assert http == loader.get_component(hass, 'http')


async def test_component_dependencies(hass):
    """Test if we can get the proper load order of components."""
    mock_integration(hass, MockModule('mod1'))
    mock_integration(hass, MockModule('mod2', ['mod1']))
    mock_integration(hass, MockModule('mod3', ['mod2']))

    assert {'mod1', 'mod2', 'mod3'} == \
        await loader.async_component_dependencies(hass, 'mod3')

    # Create circular dependency
    mock_integration(hass, MockModule('mod1', ['mod3']))

    with pytest.raises(loader.CircularDependency):
        print(await loader.async_component_dependencies(hass, 'mod3'))

    # Depend on non-existing component
    mock_integration(hass, MockModule('mod1', ['nonexisting']))

    with pytest.raises(loader.IntegrationNotFound):
        print(await loader.async_component_dependencies(hass, 'mod1'))

    # Try to get dependencies for non-existing component
    with pytest.raises(loader.IntegrationNotFound):
        print(await loader.async_component_dependencies(hass, 'nonexisting'))


def test_component_loader(hass):
    """Test loading components."""
    components = loader.Components(hass)
    assert components.http.CONFIG_SCHEMA is http.CONFIG_SCHEMA
    assert hass.components.http.CONFIG_SCHEMA is http.CONFIG_SCHEMA


def test_component_loader_non_existing(hass):
    """Test loading components."""
    components = loader.Components(hass)
    with pytest.raises(ImportError):
        components.non_existing


async def test_component_wrapper(hass):
    """Test component wrapper."""
    calls = async_mock_service(hass, 'persistent_notification', 'create')

    components = loader.Components(hass)
    components.persistent_notification.async_create('message')
    await hass.async_block_till_done()

    assert len(calls) == 1


async def test_helpers_wrapper(hass):
    """Test helpers wrapper."""
    helpers = loader.Helpers(hass)

    result = []

    def discovery_callback(service, discovered):
        """Handle discovery callback."""
        result.append(discovered)

    helpers.discovery.async_listen('service_name', discovery_callback)

    await helpers.discovery.async_discover('service_name', 'hello')
    await hass.async_block_till_done()

    assert result == ['hello']


async def test_custom_component_name(hass):
    """Test the name attribte of custom components."""
    comp = loader.get_component(hass, 'test_standalone')
    assert comp.__name__ == 'custom_components.test_standalone'
    assert comp.__package__ == 'custom_components'

    comp = loader.get_component(hass, 'test_package')
    assert comp.__name__ == 'custom_components.test_package'
    assert comp.__package__ == 'custom_components.test_package'

    comp = loader.get_component(hass, 'test.light')
    assert comp.__name__ == 'custom_components.test.light'
    assert comp.__package__ == 'custom_components.test'

    # Test custom components is mounted
    from custom_components.test_package import TEST
    assert TEST == 5


async def test_log_warning_custom_component(hass, caplog):
    """Test that we log a warning when loading a custom component."""
    loader.get_component(hass, 'test_standalone')
    assert \
        'You are using a custom component for test_standalone' in caplog.text

    loader.get_component(hass, 'test.light')
    assert 'You are using a custom component for test.light' in caplog.text


async def test_get_platform(hass, caplog):
    """Test get_platform."""
    # Test we prefer embedded over normal platforms."""
    embedded_platform = loader.get_platform(hass, 'switch', 'test_embedded')
    assert embedded_platform.__name__ == \
        'custom_components.test_embedded.switch'

    caplog.clear()

    legacy_platform = loader.get_platform(hass, 'switch', 'test_legacy')
    assert legacy_platform.__name__ == 'custom_components.switch.test_legacy'
    assert 'Integrations need to be in their own folder.' in caplog.text


async def test_get_platform_enforces_component_path(hass, caplog):
    """Test that existence of a component limits lookup path of platforms."""
    assert loader.get_platform(hass, 'comp_path_test', 'hue') is None
    assert ('Search path was limited to path of component: '
            'homeassistant.components') in caplog.text


async def test_get_integration(hass):
    """Test resolving integration."""
    integration = await loader.async_get_integration(hass, 'hue')
    assert hue == integration.get_component()
    assert hue_light == integration.get_platform('light')


async def test_get_integration_legacy(hass):
    """Test resolving integration."""
    integration = await loader.async_get_integration(hass, 'test_embedded')
    assert integration.get_component().DOMAIN == 'test_embedded'
    assert integration.get_platform('switch') is not None


async def test_get_integration_custom_component(hass):
    """Test resolving integration."""
    integration = await loader.async_get_integration(hass, 'test_package')
    print(integration)
    assert integration.get_component().DOMAIN == 'test_package'
    assert integration.name == 'Test Package'


def test_integration_properties(hass):
    """Test integration properties."""
    integration = loader.Integration(
        hass, 'homeassistant.components.hue', None, {
            'name': 'Philips Hue',
            'domain': 'hue',
            'dependencies': ['test-dep'],
            'requirements': ['test-req==1.0.0'],
        })
    assert integration.name == "Philips Hue"
    assert integration.domain == 'hue'
    assert integration.dependencies == ['test-dep']
    assert integration.requirements == ['test-req==1.0.0']
