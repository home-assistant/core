"""Test to verify that we can load components."""
import pytest

from homeassistant.components import http, hue
from homeassistant.components.hue import light as hue_light
import homeassistant.loader as loader

from tests.async_mock import ANY, patch
from tests.common import MockModule, async_mock_service, mock_integration


async def test_component_dependencies(hass):
    """Test if we can get the proper load order of components."""
    mock_integration(hass, MockModule("mod1"))
    mock_integration(hass, MockModule("mod2", ["mod1"]))
    mock_integration(hass, MockModule("mod3", ["mod2"]))

    assert {"mod1", "mod2", "mod3"} == await loader.async_component_dependencies(
        hass, "mod3"
    )

    # Create circular dependency
    mock_integration(hass, MockModule("mod1", ["mod3"]))

    with pytest.raises(loader.CircularDependency):
        print(await loader.async_component_dependencies(hass, "mod3"))

    # Depend on non-existing component
    mock_integration(hass, MockModule("mod1", ["nonexisting"]))

    with pytest.raises(loader.IntegrationNotFound):
        print(await loader.async_component_dependencies(hass, "mod1"))

    # Try to get dependencies for non-existing component
    with pytest.raises(loader.IntegrationNotFound):
        print(await loader.async_component_dependencies(hass, "nonexisting"))


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
    calls = async_mock_service(hass, "persistent_notification", "create")

    components = loader.Components(hass)
    components.persistent_notification.async_create("message")
    await hass.async_block_till_done()

    assert len(calls) == 1


async def test_helpers_wrapper(hass):
    """Test helpers wrapper."""
    helpers = loader.Helpers(hass)

    result = []

    def discovery_callback(service, discovered):
        """Handle discovery callback."""
        result.append(discovered)

    helpers.discovery.async_listen("service_name", discovery_callback)

    await helpers.discovery.async_discover("service_name", "hello", None, {})
    await hass.async_block_till_done()

    assert result == ["hello"]


async def test_custom_component_name(hass):
    """Test the name attribte of custom components."""
    integration = await loader.async_get_integration(hass, "test_standalone")
    int_comp = integration.get_component()
    assert int_comp.__name__ == "custom_components.test_standalone"
    assert int_comp.__package__ == "custom_components"

    comp = hass.components.test_standalone
    assert comp.__name__ == "custom_components.test_standalone"
    assert comp.__package__ == "custom_components"

    integration = await loader.async_get_integration(hass, "test_package")
    int_comp = integration.get_component()
    assert int_comp.__name__ == "custom_components.test_package"
    assert int_comp.__package__ == "custom_components.test_package"

    comp = hass.components.test_package
    assert comp.__name__ == "custom_components.test_package"
    assert comp.__package__ == "custom_components.test_package"

    integration = await loader.async_get_integration(hass, "test")
    platform = integration.get_platform("light")
    assert platform.__name__ == "custom_components.test.light"
    assert platform.__package__ == "custom_components.test"

    # Test custom components is mounted
    from custom_components.test_package import TEST

    assert TEST == 5


async def test_log_warning_custom_component(hass, caplog):
    """Test that we log a warning when loading a custom component."""
    hass.components.test_standalone
    assert "You are using a custom integration for test_standalone" in caplog.text

    await loader.async_get_integration(hass, "test")
    assert "You are using a custom integration for test " in caplog.text


async def test_get_integration(hass):
    """Test resolving integration."""
    integration = await loader.async_get_integration(hass, "hue")
    assert hue == integration.get_component()
    assert hue_light == integration.get_platform("light")


async def test_get_integration_legacy(hass):
    """Test resolving integration."""
    integration = await loader.async_get_integration(hass, "test_embedded")
    assert integration.get_component().DOMAIN == "test_embedded"
    assert integration.get_platform("switch") is not None


async def test_get_integration_custom_component(hass):
    """Test resolving integration."""
    integration = await loader.async_get_integration(hass, "test_package")
    print(integration)
    assert integration.get_component().DOMAIN == "test_package"
    assert integration.name == "Test Package"


def test_integration_properties(hass):
    """Test integration properties."""
    integration = loader.Integration(
        hass,
        "homeassistant.components.hue",
        None,
        {
            "name": "Philips Hue",
            "domain": "hue",
            "dependencies": ["test-dep"],
            "requirements": ["test-req==1.0.0"],
        },
    )
    assert integration.name == "Philips Hue"
    assert integration.domain == "hue"
    assert integration.dependencies == ["test-dep"]
    assert integration.requirements == ["test-req==1.0.0"]
    assert integration.is_built_in is True

    integration = loader.Integration(
        hass,
        "custom_components.hue",
        None,
        {
            "name": "Philips Hue",
            "domain": "hue",
            "dependencies": ["test-dep"],
            "requirements": ["test-req==1.0.0"],
        },
    )
    assert integration.is_built_in is False


async def test_integrations_only_once(hass):
    """Test that we load integrations only once."""
    int_1 = hass.async_create_task(loader.async_get_integration(hass, "hue"))
    int_2 = hass.async_create_task(loader.async_get_integration(hass, "hue"))

    assert await int_1 is await int_2


async def test_get_custom_components_internal(hass):
    """Test that we can a list of custom components."""
    # pylint: disable=protected-access
    integrations = await loader._async_get_custom_components(hass)
    assert integrations == {"test": ANY, "test_package": ANY}


def _get_test_integration(hass, name, config_flow):
    """Return a generated test integration."""
    return loader.Integration(
        hass,
        f"homeassistant.components.{name}",
        None,
        {
            "name": name,
            "domain": name,
            "config_flow": config_flow,
            "dependencies": [],
            "requirements": [],
        },
    )


async def test_get_custom_components(hass):
    """Verify that custom components are cached."""
    test_1_integration = _get_test_integration(hass, "test_1", False)
    test_2_integration = _get_test_integration(hass, "test_2", True)

    name = "homeassistant.loader._async_get_custom_components"
    with patch(name) as mock_get:
        mock_get.return_value = {
            "test_1": test_1_integration,
            "test_2": test_2_integration,
        }
        integrations = await loader.async_get_custom_components(hass)
        assert integrations == mock_get.return_value
        integrations = await loader.async_get_custom_components(hass)
        assert integrations == mock_get.return_value
        mock_get.assert_called_once_with(hass)


async def test_get_config_flows(hass):
    """Verify that custom components with config_flow are available."""
    test_1_integration = _get_test_integration(hass, "test_1", False)
    test_2_integration = _get_test_integration(hass, "test_2", True)

    with patch("homeassistant.loader.async_get_custom_components") as mock_get:
        mock_get.return_value = {
            "test_1": test_1_integration,
            "test_2": test_2_integration,
        }
        flows = await loader.async_get_config_flows(hass)
        assert "test_2" in flows
        assert "test_1" not in flows


async def test_get_custom_components_safe_mode(hass):
    """Test that we get empty custom components in safe mode."""
    hass.config.safe_mode = True
    assert await loader.async_get_custom_components(hass) == {}
