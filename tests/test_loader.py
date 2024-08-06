"""Test to verify that we can load components."""

import asyncio
import os
import pathlib
import sys
import threading
from typing import Any
from unittest.mock import MagicMock, Mock, patch

from awesomeversion import AwesomeVersion
import pytest

from homeassistant import loader
from homeassistant.components import http, hue
from homeassistant.components.hue import light as hue_light
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import frame
from homeassistant.helpers.json import json_dumps
from homeassistant.util.json import json_loads

from .common import MockModule, async_get_persistent_notifications, mock_integration


async def test_circular_component_dependencies(hass: HomeAssistant) -> None:
    """Test if we can detect circular dependencies of components."""
    mock_integration(hass, MockModule("mod1"))
    mock_integration(hass, MockModule("mod2", dependencies=["mod1"]))
    mock_integration(hass, MockModule("mod3", dependencies=["mod1"]))
    mod_4 = mock_integration(hass, MockModule("mod4", dependencies=["mod2", "mod3"]))

    deps = await loader._async_component_dependencies(hass, mod_4)
    assert deps == {"mod1", "mod2", "mod3", "mod4"}

    # Create a circular dependency
    mock_integration(hass, MockModule("mod1", dependencies=["mod4"]))
    with pytest.raises(loader.CircularDependency):
        await loader._async_component_dependencies(hass, mod_4)

    # Create a different circular dependency
    mock_integration(hass, MockModule("mod1", dependencies=["mod3"]))
    with pytest.raises(loader.CircularDependency):
        await loader._async_component_dependencies(hass, mod_4)

    # Create a circular after_dependency
    mock_integration(
        hass, MockModule("mod1", partial_manifest={"after_dependencies": ["mod4"]})
    )
    with pytest.raises(loader.CircularDependency):
        await loader._async_component_dependencies(hass, mod_4)

    # Create a different circular after_dependency
    mock_integration(
        hass, MockModule("mod1", partial_manifest={"after_dependencies": ["mod3"]})
    )
    with pytest.raises(loader.CircularDependency):
        await loader._async_component_dependencies(hass, mod_4)


async def test_nonexistent_component_dependencies(hass: HomeAssistant) -> None:
    """Test if we can detect nonexistent dependencies of components."""
    mod_1 = mock_integration(hass, MockModule("mod1", dependencies=["nonexistent"]))
    with pytest.raises(loader.IntegrationNotFound):
        await loader._async_component_dependencies(hass, mod_1)


def test_component_loader(hass: HomeAssistant) -> None:
    """Test loading components."""
    components = loader.Components(hass)
    assert components.http.CONFIG_SCHEMA is http.CONFIG_SCHEMA
    assert hass.components.http.CONFIG_SCHEMA is http.CONFIG_SCHEMA


def test_component_loader_non_existing(hass: HomeAssistant) -> None:
    """Test loading components."""
    components = loader.Components(hass)
    with pytest.raises(ImportError):
        _ = components.non_existing


async def test_component_wrapper(hass: HomeAssistant) -> None:
    """Test component wrapper."""
    components = loader.Components(hass)
    components.persistent_notification.async_create("message")

    notifications = async_get_persistent_notifications(hass)
    assert len(notifications)


async def test_helpers_wrapper(hass: HomeAssistant) -> None:
    """Test helpers wrapper."""
    helpers = loader.Helpers(hass)

    result = []

    @callback
    def discovery_callback(service, discovered):
        """Handle discovery callback."""
        result.append(discovered)

    helpers.discovery.async_listen("service_name", discovery_callback)

    await helpers.discovery.async_discover("service_name", "hello", None, {})
    await hass.async_block_till_done()

    assert result == ["hello"]


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_custom_component_name(hass: HomeAssistant) -> None:
    """Test the name attribute of custom components."""
    with pytest.raises(loader.IntegrationNotFound):
        await loader.async_get_integration(hass, "test_standalone")

    integration = await loader.async_get_integration(hass, "test_package")

    int_comp = integration.get_component()
    assert int_comp.__name__ == "custom_components.test_package"
    assert int_comp.__package__ == "custom_components.test_package"

    comp = hass.components.test_package
    assert comp.__name__ == "custom_components.test_package"
    assert comp.__package__ == "custom_components.test_package"

    integration = await loader.async_get_integration(hass, "test")
    platform = integration.get_platform("light")
    assert integration.get_platform_cached("light") is platform

    assert platform.__name__ == "custom_components.test.light"
    assert platform.__package__ == "custom_components.test"

    # Test custom components is mounted
    # pylint: disable-next=import-outside-toplevel
    from custom_components.test_package import TEST

    assert TEST == 5


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_log_warning_custom_component(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that we log a warning when loading a custom component."""

    await loader.async_get_integration(hass, "test_package")
    assert "We found a custom integration test_package" in caplog.text

    await loader.async_get_integration(hass, "test")
    assert "We found a custom integration test " in caplog.text


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_custom_integration_version_not_valid(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that we log a warning when custom integrations have a invalid version."""
    with pytest.raises(loader.IntegrationNotFound):
        await loader.async_get_integration(hass, "test_no_version")

    assert (
        "The custom integration 'test_no_version' does not have a version key in the"
        " manifest file and was blocked from loading."
    ) in caplog.text

    with pytest.raises(loader.IntegrationNotFound):
        await loader.async_get_integration(hass, "test2")
    assert (
        "The custom integration 'test_bad_version' does not have a valid version key"
        " (bad) in the manifest file and was blocked from loading."
    ) in caplog.text


@pytest.mark.parametrize(
    "blocked_versions",
    [
        loader.BlockedIntegration(None, "breaks Home Assistant"),
        loader.BlockedIntegration(AwesomeVersion("2.0.0"), "breaks Home Assistant"),
    ],
)
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_custom_integration_version_blocked(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    blocked_versions,
) -> None:
    """Test that we log a warning when custom integrations have a blocked version."""
    with patch.dict(
        loader.BLOCKED_CUSTOM_INTEGRATIONS, {"test_blocked_version": blocked_versions}
    ):
        with pytest.raises(loader.IntegrationNotFound):
            await loader.async_get_integration(hass, "test_blocked_version")

        assert (
            "Version 1.0.0 of custom integration 'test_blocked_version' breaks"
            " Home Assistant and was blocked from loading, please report it to the"
            " author of the 'test_blocked_version' custom integration"
        ) in caplog.text


@pytest.mark.parametrize(
    "blocked_versions",
    [
        loader.BlockedIntegration(AwesomeVersion("0.9.9"), "breaks Home Assistant"),
        loader.BlockedIntegration(AwesomeVersion("1.0.0"), "breaks Home Assistant"),
    ],
)
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_custom_integration_version_not_blocked(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    blocked_versions,
) -> None:
    """Test that we log a warning when custom integrations have a blocked version."""
    with patch.dict(
        loader.BLOCKED_CUSTOM_INTEGRATIONS, {"test_blocked_version": blocked_versions}
    ):
        await loader.async_get_integration(hass, "test_blocked_version")

        assert (
            "Version 1.0.0 of custom integration 'test_blocked_version'"
        ) not in caplog.text


async def test_get_integration(hass: HomeAssistant) -> None:
    """Test resolving integration."""
    with pytest.raises(loader.IntegrationNotLoaded):
        loader.async_get_loaded_integration(hass, "hue")

    integration = await loader.async_get_integration(hass, "hue")
    assert hue == integration.get_component()
    assert hue_light == integration.get_platform("light")

    integration = loader.async_get_loaded_integration(hass, "hue")
    assert hue == integration.get_component()
    assert hue_light == integration.get_platform("light")


async def test_async_get_component(hass: HomeAssistant) -> None:
    """Test resolving integration."""
    with pytest.raises(loader.IntegrationNotLoaded):
        loader.async_get_loaded_integration(hass, "hue")

    integration = await loader.async_get_integration(hass, "hue")
    assert await integration.async_get_component() == hue
    assert integration.get_platform("light") == hue_light

    integration = loader.async_get_loaded_integration(hass, "hue")
    assert await integration.async_get_component() == hue
    assert integration.get_platform("light") == hue_light


async def test_get_integration_exceptions(hass: HomeAssistant) -> None:
    """Test resolving integration."""
    integration = await loader.async_get_integration(hass, "hue")

    with (
        pytest.raises(ImportError),
        patch(
            "homeassistant.loader.importlib.import_module",
            side_effect=ValueError("Boom"),
        ),
    ):
        assert hue == integration.get_component()

    with (
        pytest.raises(ImportError),
        patch(
            "homeassistant.loader.importlib.import_module",
            side_effect=ValueError("Boom"),
        ),
    ):
        assert hue_light == integration.get_platform("light")


async def test_get_platform_caches_failures_when_component_loaded(
    hass: HomeAssistant,
) -> None:
    """Test get_platform caches failures only when the component is loaded.

    Only ModuleNotFoundError is cached, ImportError is not cached.
    """
    integration = await loader.async_get_integration(hass, "hue")

    with (
        pytest.raises(ModuleNotFoundError),
        patch(
            "homeassistant.loader.importlib.import_module",
            side_effect=ModuleNotFoundError("Boom"),
        ),
    ):
        assert integration.get_component() == hue

    with (
        pytest.raises(ModuleNotFoundError),
        patch(
            "homeassistant.loader.importlib.import_module",
            side_effect=ModuleNotFoundError("Boom"),
        ),
    ):
        assert integration.get_platform("light") == hue_light

    # Hue is not loaded so we should still hit the import_module path
    with (
        pytest.raises(ModuleNotFoundError),
        patch(
            "homeassistant.loader.importlib.import_module",
            side_effect=ModuleNotFoundError("Boom"),
        ),
    ):
        assert integration.get_platform("light") == hue_light

    assert integration.get_component() == hue

    # Hue is loaded so we should cache the import_module failure now
    with (
        pytest.raises(ModuleNotFoundError),
        patch(
            "homeassistant.loader.importlib.import_module",
            side_effect=ModuleNotFoundError("Boom"),
        ),
    ):
        assert integration.get_platform("light") == hue_light

    # Hue is loaded and the last call should have cached the import_module failure
    with pytest.raises(ModuleNotFoundError):
        assert integration.get_platform("light") == hue_light


async def test_get_platform_only_cached_module_not_found_when_component_loaded(
    hass: HomeAssistant,
) -> None:
    """Test get_platform cache only cache module not found when the component is loaded."""
    integration = await loader.async_get_integration(hass, "hue")

    with (
        pytest.raises(ImportError),
        patch(
            "homeassistant.loader.importlib.import_module",
            side_effect=ImportError("Boom"),
        ),
    ):
        assert integration.get_component() == hue

    with (
        pytest.raises(ImportError),
        patch(
            "homeassistant.loader.importlib.import_module",
            side_effect=ImportError("Boom"),
        ),
    ):
        assert integration.get_platform("light") == hue_light

    # Hue is not loaded so we should still hit the import_module path
    with (
        pytest.raises(ImportError),
        patch(
            "homeassistant.loader.importlib.import_module",
            side_effect=ImportError("Boom"),
        ),
    ):
        assert integration.get_platform("light") == hue_light

    assert integration.get_component() == hue

    # Hue is loaded so we should cache the import_module failure now
    with (
        pytest.raises(ImportError),
        patch(
            "homeassistant.loader.importlib.import_module",
            side_effect=ImportError("Boom"),
        ),
    ):
        assert integration.get_platform("light") == hue_light

    # ImportError is not cached because we only cache ModuleNotFoundError
    assert integration.get_platform("light") == hue_light


async def test_async_get_platform_caches_failures_when_component_loaded(
    hass: HomeAssistant,
) -> None:
    """Test async_get_platform caches failures only when the component is loaded.

    Only ModuleNotFoundError is cached, ImportError is not cached.
    """
    integration = await loader.async_get_integration(hass, "hue")

    with (
        pytest.raises(ModuleNotFoundError),
        patch(
            "homeassistant.loader.importlib.import_module",
            side_effect=ModuleNotFoundError("Boom"),
        ),
    ):
        assert integration.get_component() == hue

    with (
        pytest.raises(ModuleNotFoundError),
        patch(
            "homeassistant.loader.importlib.import_module",
            side_effect=ModuleNotFoundError("Boom"),
        ),
    ):
        assert await integration.async_get_platform("light") == hue_light

    # Hue is not loaded so we should still hit the import_module path
    with (
        pytest.raises(ModuleNotFoundError),
        patch(
            "homeassistant.loader.importlib.import_module",
            side_effect=ModuleNotFoundError("Boom"),
        ),
    ):
        assert await integration.async_get_platform("light") == hue_light

    assert integration.get_component() == hue

    # Hue is loaded so we should cache the import_module failure now
    with (
        pytest.raises(ModuleNotFoundError),
        patch(
            "homeassistant.loader.importlib.import_module",
            side_effect=ModuleNotFoundError("Boom"),
        ),
    ):
        assert await integration.async_get_platform("light") == hue_light

    # Hue is loaded and the last call should have cached the import_module failure
    with pytest.raises(ModuleNotFoundError):
        assert await integration.async_get_platform("light") == hue_light

    # The cache should never be filled because the import error is remembered
    assert integration.get_platform_cached("light") is None


async def test_async_get_platforms_caches_failures_when_component_loaded(
    hass: HomeAssistant,
) -> None:
    """Test async_get_platforms cache failures only when the component is loaded.

    Only ModuleNotFoundError is cached, ImportError is not cached.
    """
    integration = await loader.async_get_integration(hass, "hue")

    with (
        pytest.raises(ModuleNotFoundError),
        patch(
            "homeassistant.loader.importlib.import_module",
            side_effect=ModuleNotFoundError("Boom"),
        ),
    ):
        assert integration.get_component() == hue

    with (
        pytest.raises(ModuleNotFoundError),
        patch(
            "homeassistant.loader.importlib.import_module",
            side_effect=ModuleNotFoundError("Boom"),
        ),
    ):
        assert await integration.async_get_platforms(["light"]) == {"light": hue_light}

    # Hue is not loaded so we should still hit the import_module path
    with (
        pytest.raises(ModuleNotFoundError),
        patch(
            "homeassistant.loader.importlib.import_module",
            side_effect=ModuleNotFoundError("Boom"),
        ),
    ):
        assert await integration.async_get_platforms(["light"]) == {"light": hue_light}

    assert integration.get_component() == hue

    # Hue is loaded so we should cache the import_module failure now
    with (
        pytest.raises(ModuleNotFoundError),
        patch(
            "homeassistant.loader.importlib.import_module",
            side_effect=ModuleNotFoundError("Boom"),
        ),
    ):
        assert await integration.async_get_platforms(["light"]) == {"light": hue_light}

    # Hue is loaded and the last call should have cached the import_module failure
    with pytest.raises(ModuleNotFoundError):
        assert await integration.async_get_platforms(["light"]) == {"light": hue_light}

    # The cache should never be filled because the import error is remembered
    assert integration.get_platform_cached("light") is None


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_get_integration_legacy(hass: HomeAssistant) -> None:
    """Test resolving integration."""
    integration = await loader.async_get_integration(hass, "test_embedded")
    assert integration.get_component().DOMAIN == "test_embedded"
    assert integration.get_platform("switch") is not None
    assert integration.get_platform_cached("switch") is not None


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_get_integration_custom_component(hass: HomeAssistant) -> None:
    """Test resolving integration."""
    integration = await loader.async_get_integration(hass, "test_package")

    assert integration.get_component().DOMAIN == "test_package"
    assert integration.name == "Test Package"


def test_integration_properties(hass: HomeAssistant) -> None:
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
            "zeroconf": ["_hue._tcp.local."],
            "homekit": {"models": ["BSB002"]},
            "dhcp": [
                {"hostname": "tesla_*", "macaddress": "4CFCAA*"},
                {"hostname": "tesla_*", "macaddress": "044EAF*"},
                {"hostname": "tesla_*", "macaddress": "98ED5C*"},
                {"registered_devices": True},
            ],
            "bluetooth": [{"manufacturer_id": 76, "manufacturer_data_start": [0x06]}],
            "usb": [
                {"vid": "10C4", "pid": "EA60"},
                {"vid": "1CF1", "pid": "0030"},
                {"vid": "1A86", "pid": "7523"},
                {"vid": "10C4", "pid": "8A2A"},
            ],
            "ssdp": [
                {
                    "manufacturer": "Royal Philips Electronics",
                    "modelName": "Philips hue bridge 2012",
                },
                {
                    "manufacturer": "Royal Philips Electronics",
                    "modelName": "Philips hue bridge 2015",
                },
                {"manufacturer": "Signify", "modelName": "Philips hue bridge 2015"},
            ],
            "mqtt": ["hue/discovery"],
            "version": "1.0.0",
        },
    )
    assert integration.name == "Philips Hue"
    assert integration.domain == "hue"
    assert integration.homekit == {"models": ["BSB002"]}
    assert integration.zeroconf == ["_hue._tcp.local."]
    assert integration.dhcp == [
        {"hostname": "tesla_*", "macaddress": "4CFCAA*"},
        {"hostname": "tesla_*", "macaddress": "044EAF*"},
        {"hostname": "tesla_*", "macaddress": "98ED5C*"},
        {"registered_devices": True},
    ]
    assert integration.usb == [
        {"vid": "10C4", "pid": "EA60"},
        {"vid": "1CF1", "pid": "0030"},
        {"vid": "1A86", "pid": "7523"},
        {"vid": "10C4", "pid": "8A2A"},
    ]
    assert integration.bluetooth == [
        {"manufacturer_id": 76, "manufacturer_data_start": [0x06]}
    ]
    assert integration.ssdp == [
        {
            "manufacturer": "Royal Philips Electronics",
            "modelName": "Philips hue bridge 2012",
        },
        {
            "manufacturer": "Royal Philips Electronics",
            "modelName": "Philips hue bridge 2015",
        },
        {"manufacturer": "Signify", "modelName": "Philips hue bridge 2015"},
    ]
    assert integration.mqtt == ["hue/discovery"]
    assert integration.dependencies == ["test-dep"]
    assert integration.requirements == ["test-req==1.0.0"]
    assert integration.is_built_in is True
    assert integration.version == "1.0.0"

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
    assert integration.homekit is None
    assert integration.zeroconf is None
    assert integration.dhcp is None
    assert integration.bluetooth is None
    assert integration.usb is None
    assert integration.ssdp is None
    assert integration.mqtt is None
    assert integration.version is None

    integration = loader.Integration(
        hass,
        "custom_components.hue",
        None,
        {
            "name": "Philips Hue",
            "domain": "hue",
            "dependencies": ["test-dep"],
            "zeroconf": [{"type": "_hue._tcp.local.", "name": "hue*"}],
            "requirements": ["test-req==1.0.0"],
        },
    )
    assert integration.is_built_in is False
    assert integration.homekit is None
    assert integration.zeroconf == [{"type": "_hue._tcp.local.", "name": "hue*"}]
    assert integration.dhcp is None
    assert integration.usb is None
    assert integration.bluetooth is None
    assert integration.ssdp is None


async def test_integrations_only_once(hass: HomeAssistant) -> None:
    """Test that we load integrations only once."""
    int_1 = hass.async_create_task(loader.async_get_integration(hass, "hue"))
    int_2 = hass.async_create_task(loader.async_get_integration(hass, "hue"))

    assert await int_1 is await int_2


def _get_test_integration(
    hass: HomeAssistant, name: str, config_flow: bool, import_executor: bool = False
) -> loader.Integration:
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
            "zeroconf": [f"_{name}._tcp.local."],
            "homekit": {"models": [name]},
            "ssdp": [{"manufacturer": name, "modelName": name}],
            "mqtt": [f"{name}/discovery"],
            "import_executor": import_executor,
        },
    )


def _get_test_integration_with_application_credentials(hass, name):
    """Return a generated test integration with application_credentials support."""
    return loader.Integration(
        hass,
        f"homeassistant.components.{name}",
        None,
        {
            "name": name,
            "domain": name,
            "config_flow": True,
            "dependencies": ["application_credentials"],
            "requirements": [],
            "zeroconf": [f"_{name}._tcp.local."],
            "homekit": {"models": [name]},
            "ssdp": [{"manufacturer": name, "modelName": name}],
            "mqtt": [f"{name}/discovery"],
        },
    )


def _get_test_integration_with_zeroconf_matcher(hass, name, config_flow):
    """Return a generated test integration with a zeroconf matcher."""
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
            "zeroconf": [{"type": f"_{name}._tcp.local.", "name": f"{name}*"}],
            "homekit": {"models": [name]},
            "ssdp": [{"manufacturer": name, "modelName": name}],
        },
    )


def _get_test_integration_with_legacy_zeroconf_matcher(hass, name, config_flow):
    """Return a generated test integration with a legacy zeroconf matcher."""
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
            "zeroconf": [
                {
                    "type": f"_{name}._tcp.local.",
                    "macaddress": "AABBCC*",
                    "manufacturer": "legacy*",
                    "model": "legacy*",
                    "name": f"{name}*",
                }
            ],
            "homekit": {"models": [name]},
            "ssdp": [{"manufacturer": name, "modelName": name}],
        },
    )


def _get_test_integration_with_dhcp_matcher(hass, name, config_flow):
    """Return a generated test integration with a dhcp matcher."""
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
            "zeroconf": [],
            "dhcp": [
                {"hostname": "tesla_*", "macaddress": "4CFCAA*"},
                {"hostname": "tesla_*", "macaddress": "044EAF*"},
                {"hostname": "tesla_*", "macaddress": "98ED5C*"},
            ],
            "homekit": {"models": [name]},
            "ssdp": [{"manufacturer": name, "modelName": name}],
        },
    )


def _get_test_integration_with_bluetooth_matcher(hass, name, config_flow):
    """Return a generated test integration with a bluetooth matcher."""
    return loader.Integration(
        hass,
        f"homeassistant.components.{name}",
        None,
        {
            "name": name,
            "domain": name,
            "config_flow": config_flow,
            "bluetooth": [
                {
                    "local_name": "Prodigio_*",
                },
            ],
        },
    )


def _get_test_integration_with_usb_matcher(hass, name, config_flow):
    """Return a generated test integration with a usb matcher."""
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
            "usb": [
                {
                    "vid": "10C4",
                    "pid": "EA60",
                    "known_devices": ["slae.sh cc2652rb stick"],
                },
                {"vid": "1CF1", "pid": "0030", "known_devices": ["Conbee II"]},
                {
                    "vid": "1A86",
                    "pid": "7523",
                    "known_devices": ["Electrolama zig-a-zig-ah"],
                },
                {"vid": "10C4", "pid": "8A2A", "known_devices": ["Nortek HUSBZB-1"]},
            ],
        },
    )


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_get_custom_components(hass: HomeAssistant) -> None:
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


async def test_get_config_flows(hass: HomeAssistant) -> None:
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


async def test_get_zeroconf(hass: HomeAssistant) -> None:
    """Verify that custom components with zeroconf are found."""
    test_1_integration = _get_test_integration(hass, "test_1", True)
    test_2_integration = _get_test_integration_with_zeroconf_matcher(
        hass, "test_2", True
    )

    with patch("homeassistant.loader.async_get_custom_components") as mock_get:
        mock_get.return_value = {
            "test_1": test_1_integration,
            "test_2": test_2_integration,
        }
        zeroconf = await loader.async_get_zeroconf(hass)
        assert zeroconf["_test_1._tcp.local."] == [{"domain": "test_1"}]
        assert zeroconf["_test_2._tcp.local."] == [
            {"domain": "test_2", "name": "test_2*"}
        ]


async def test_get_application_credentials(hass: HomeAssistant) -> None:
    """Verify that custom components with application_credentials are found."""
    test_1_integration = _get_test_integration(hass, "test_1", True)
    test_2_integration = _get_test_integration_with_application_credentials(
        hass, "test_2"
    )

    with patch("homeassistant.loader.async_get_custom_components") as mock_get:
        mock_get.return_value = {
            "test_1": test_1_integration,
            "test_2": test_2_integration,
        }
        application_credentials = await loader.async_get_application_credentials(hass)
        assert "test_2" in application_credentials
        assert "test_1" not in application_credentials


async def test_get_zeroconf_back_compat(hass: HomeAssistant) -> None:
    """Verify that custom components with zeroconf are found and legacy matchers are converted."""
    test_1_integration = _get_test_integration(hass, "test_1", True)
    test_2_integration = _get_test_integration_with_legacy_zeroconf_matcher(
        hass, "test_2", True
    )

    with patch("homeassistant.loader.async_get_custom_components") as mock_get:
        mock_get.return_value = {
            "test_1": test_1_integration,
            "test_2": test_2_integration,
        }
        zeroconf = await loader.async_get_zeroconf(hass)
        assert zeroconf["_test_1._tcp.local."] == [{"domain": "test_1"}]
        assert zeroconf["_test_2._tcp.local."] == [
            {
                "domain": "test_2",
                "name": "test_2*",
                "properties": {
                    "macaddress": "aabbcc*",
                    "model": "legacy*",
                    "manufacturer": "legacy*",
                },
            }
        ]


async def test_get_bluetooth(hass: HomeAssistant) -> None:
    """Verify that custom components with bluetooth are found."""
    test_1_integration = _get_test_integration_with_bluetooth_matcher(
        hass, "test_1", True
    )
    test_2_integration = _get_test_integration_with_dhcp_matcher(hass, "test_2", True)
    with patch("homeassistant.loader.async_get_custom_components") as mock_get:
        mock_get.return_value = {
            "test_1": test_1_integration,
            "test_2": test_2_integration,
        }
        bluetooth = await loader.async_get_bluetooth(hass)
        bluetooth_for_domain = [
            entry for entry in bluetooth if entry["domain"] == "test_1"
        ]
        assert bluetooth_for_domain == [
            {"domain": "test_1", "local_name": "Prodigio_*"},
        ]


async def test_get_dhcp(hass: HomeAssistant) -> None:
    """Verify that custom components with dhcp are found."""
    test_1_integration = _get_test_integration_with_dhcp_matcher(hass, "test_1", True)

    with patch("homeassistant.loader.async_get_custom_components") as mock_get:
        mock_get.return_value = {
            "test_1": test_1_integration,
        }
        dhcp = await loader.async_get_dhcp(hass)
        dhcp_for_domain = [entry for entry in dhcp if entry["domain"] == "test_1"]
        assert dhcp_for_domain == [
            {"domain": "test_1", "hostname": "tesla_*", "macaddress": "4CFCAA*"},
            {"domain": "test_1", "hostname": "tesla_*", "macaddress": "044EAF*"},
            {"domain": "test_1", "hostname": "tesla_*", "macaddress": "98ED5C*"},
        ]


async def test_get_usb(hass: HomeAssistant) -> None:
    """Verify that custom components with usb matchers are found."""
    test_1_integration = _get_test_integration_with_usb_matcher(hass, "test_1", True)

    with patch("homeassistant.loader.async_get_custom_components") as mock_get:
        mock_get.return_value = {
            "test_1": test_1_integration,
        }
        usb = await loader.async_get_usb(hass)
        usb_for_domain = [entry for entry in usb if entry["domain"] == "test_1"]
        assert usb_for_domain == [
            {"domain": "test_1", "vid": "10C4", "pid": "EA60"},
            {"domain": "test_1", "vid": "1CF1", "pid": "0030"},
            {"domain": "test_1", "vid": "1A86", "pid": "7523"},
            {"domain": "test_1", "vid": "10C4", "pid": "8A2A"},
        ]


async def test_get_homekit(hass: HomeAssistant) -> None:
    """Verify that custom components with homekit are found."""
    test_1_integration = _get_test_integration(hass, "test_1", True)
    test_2_integration = _get_test_integration(hass, "test_2", True)

    with patch("homeassistant.loader.async_get_custom_components") as mock_get:
        mock_get.return_value = {
            "test_1": test_1_integration,
            "test_2": test_2_integration,
        }
        homekit = await loader.async_get_homekit(hass)
        assert homekit["test_1"] == loader.HomeKitDiscoveredIntegration("test_1", True)
        assert homekit["test_2"] == loader.HomeKitDiscoveredIntegration("test_2", True)


async def test_get_ssdp(hass: HomeAssistant) -> None:
    """Verify that custom components with ssdp are found."""
    test_1_integration = _get_test_integration(hass, "test_1", True)
    test_2_integration = _get_test_integration(hass, "test_2", True)

    with patch("homeassistant.loader.async_get_custom_components") as mock_get:
        mock_get.return_value = {
            "test_1": test_1_integration,
            "test_2": test_2_integration,
        }
        ssdp = await loader.async_get_ssdp(hass)
        assert ssdp["test_1"] == [{"manufacturer": "test_1", "modelName": "test_1"}]
        assert ssdp["test_2"] == [{"manufacturer": "test_2", "modelName": "test_2"}]


async def test_get_mqtt(hass: HomeAssistant) -> None:
    """Verify that custom components with MQTT are found."""
    test_1_integration = _get_test_integration(hass, "test_1", True)
    test_2_integration = _get_test_integration(hass, "test_2", True)

    with patch("homeassistant.loader.async_get_custom_components") as mock_get:
        mock_get.return_value = {
            "test_1": test_1_integration,
            "test_2": test_2_integration,
        }
        mqtt = await loader.async_get_mqtt(hass)
        assert mqtt["test_1"] == ["test_1/discovery"]
        assert mqtt["test_2"] == ["test_2/discovery"]


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_import_platform_executor(hass: HomeAssistant) -> None:
    """Test import a platform in the executor."""
    integration = await loader.async_get_integration(
        hass, "test_package_loaded_executor"
    )

    config_flow_task_1 = asyncio.create_task(
        integration.async_get_platform("config_flow")
    )
    config_flow_task_2 = asyncio.create_task(
        integration.async_get_platform("config_flow")
    )
    config_flow_task_3 = asyncio.create_task(
        integration.async_get_platform("config_flow")
    )

    config_flow_task1_result = await config_flow_task_1
    config_flow_task2_result = await config_flow_task_2
    config_flow_task3_result = await config_flow_task_3

    assert (
        config_flow_task1_result == config_flow_task2_result == config_flow_task3_result
    )

    assert await config_flow_task1_result._async_has_devices(hass) is True


async def test_get_custom_components_recovery_mode(hass: HomeAssistant) -> None:
    """Test that we get empty custom components in recovery mode."""
    hass.config.recovery_mode = True
    assert await loader.async_get_custom_components(hass) == {}


async def test_custom_integration_missing_version(hass: HomeAssistant) -> None:
    """Test trying to load a custom integration without a version twice does not deadlock."""
    with pytest.raises(loader.IntegrationNotFound):
        await loader.async_get_integration(hass, "test_no_version")

    with pytest.raises(loader.IntegrationNotFound):
        await loader.async_get_integration(hass, "test_no_version")


async def test_custom_integration_missing(hass: HomeAssistant) -> None:
    """Test trying to load a custom integration that is missing twice not deadlock."""
    with patch("homeassistant.loader.async_get_custom_components") as mock_get:
        mock_get.return_value = {}

        with pytest.raises(loader.IntegrationNotFound):
            await loader.async_get_integration(hass, "test1")

        with pytest.raises(loader.IntegrationNotFound):
            await loader.async_get_integration(hass, "test1")


async def test_validation(hass: HomeAssistant) -> None:
    """Test we raise if invalid domain passed in."""
    with pytest.raises(ValueError):
        await loader.async_get_integration(hass, "some.thing")


async def test_loggers(hass: HomeAssistant) -> None:
    """Test we can fetch the loggers from the integration."""
    name = "dummy"
    integration = loader.Integration(
        hass,
        f"homeassistant.components.{name}",
        None,
        {
            "name": name,
            "domain": name,
            "config_flow": True,
            "dependencies": [],
            "requirements": [],
            "loggers": ["name1", "name2"],
        },
    )
    assert integration.loggers == ["name1", "name2"]


CORE_ISSUE_TRACKER = (
    "https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue"
)
CORE_ISSUE_TRACKER_BUILT_IN = (
    CORE_ISSUE_TRACKER + "+label%3A%22integration%3A+bla_built_in%22"
)
CORE_ISSUE_TRACKER_CUSTOM = (
    CORE_ISSUE_TRACKER + "+label%3A%22integration%3A+bla_custom%22"
)
CORE_ISSUE_TRACKER_CUSTOM_NO_TRACKER = (
    CORE_ISSUE_TRACKER + "+label%3A%22integration%3A+bla_custom_no_tracker%22"
)
CORE_ISSUE_TRACKER_HUE = CORE_ISSUE_TRACKER + "+label%3A%22integration%3A+hue%22"
CUSTOM_ISSUE_TRACKER = "https://blablabla.com"


@pytest.mark.parametrize(
    ("domain", "module", "issue_tracker"),
    [
        # If no information is available, open issue on core
        (None, None, CORE_ISSUE_TRACKER),
        ("hue", "homeassistant.components.hue.sensor", CORE_ISSUE_TRACKER_HUE),
        ("hue", None, CORE_ISSUE_TRACKER_HUE),
        ("bla_built_in", None, CORE_ISSUE_TRACKER_BUILT_IN),
        # Integration domain is not currently deduced from module
        (None, "homeassistant.components.hue.sensor", CORE_ISSUE_TRACKER),
        ("hue", "homeassistant.components.mqtt.sensor", CORE_ISSUE_TRACKER_HUE),
        # Loaded custom integration with known issue tracker
        ("bla_custom", "custom_components.bla_custom.sensor", CUSTOM_ISSUE_TRACKER),
        ("bla_custom", None, CUSTOM_ISSUE_TRACKER),
        # Loaded custom integration without known issue tracker
        (None, "custom_components.bla.sensor", None),
        ("bla_custom_no_tracker", "custom_components.bla_custom.sensor", None),
        ("bla_custom_no_tracker", None, None),
        ("hue", "custom_components.bla.sensor", None),
        # Unloaded custom integration with known issue tracker
        ("bla_custom_not_loaded", None, CUSTOM_ISSUE_TRACKER),
        # Unloaded custom integration without known issue tracker
        ("bla_custom_not_loaded_no_tracker", None, None),
        # Integration domain has priority over module
        ("bla_custom_no_tracker", "homeassistant.components.bla_custom.sensor", None),
    ],
)
async def test_async_get_issue_tracker(
    hass: HomeAssistant,
    domain: str | None,
    module: str | None,
    issue_tracker: str | None,
) -> None:
    """Test async_get_issue_tracker."""
    mock_integration(hass, MockModule("bla_built_in"))
    mock_integration(
        hass,
        MockModule(
            "bla_custom", partial_manifest={"issue_tracker": CUSTOM_ISSUE_TRACKER}
        ),
        built_in=False,
    )
    mock_integration(hass, MockModule("bla_custom_no_tracker"), built_in=False)

    cust_unloaded_module = MockModule(
        "bla_custom_not_loaded",
        partial_manifest={"issue_tracker": CUSTOM_ISSUE_TRACKER},
    )
    cust_unloaded = loader.Integration(
        hass,
        f"{loader.PACKAGE_CUSTOM_COMPONENTS}.{cust_unloaded_module.DOMAIN}",
        pathlib.Path(""),
        cust_unloaded_module.mock_manifest(),
        set(),
    )

    cust_unloaded_no_tracker_module = MockModule("bla_custom_not_loaded_no_tracker")
    cust_unloaded_no_tracker = loader.Integration(
        hass,
        f"{loader.PACKAGE_CUSTOM_COMPONENTS}.{cust_unloaded_no_tracker_module.DOMAIN}",
        pathlib.Path(""),
        cust_unloaded_no_tracker_module.mock_manifest(),
        set(),
    )
    hass.data["custom_components"] = {
        "bla_custom_not_loaded": cust_unloaded,
        "bla_custom_not_loaded_no_tracker": cust_unloaded_no_tracker,
    }

    assert (
        loader.async_get_issue_tracker(hass, integration_domain=domain, module=module)
        == issue_tracker
    )


@pytest.mark.parametrize(
    ("domain", "module", "issue_tracker"),
    [
        # If no information is available, open issue on core
        (None, None, CORE_ISSUE_TRACKER),
        ("hue", "homeassistant.components.hue.sensor", CORE_ISSUE_TRACKER_HUE),
        ("hue", None, CORE_ISSUE_TRACKER_HUE),
        ("bla_built_in", None, CORE_ISSUE_TRACKER_BUILT_IN),
        # Integration domain is not currently deduced from module
        (None, "homeassistant.components.hue.sensor", CORE_ISSUE_TRACKER),
        ("hue", "homeassistant.components.mqtt.sensor", CORE_ISSUE_TRACKER_HUE),
        # Custom integration with known issue tracker - can't find it without hass
        ("bla_custom", "custom_components.bla_custom.sensor", None),
        # Assumed to be a core integration without hass and without module
        ("bla_custom", None, CORE_ISSUE_TRACKER_CUSTOM),
    ],
)
async def test_async_get_issue_tracker_no_hass(
    hass: HomeAssistant, domain: str | None, module: str | None, issue_tracker: str
) -> None:
    """Test async_get_issue_tracker."""
    mock_integration(hass, MockModule("bla_built_in"))
    mock_integration(
        hass,
        MockModule(
            "bla_custom", partial_manifest={"issue_tracker": CUSTOM_ISSUE_TRACKER}
        ),
        built_in=False,
    )
    assert (
        loader.async_get_issue_tracker(None, integration_domain=domain, module=module)
        == issue_tracker
    )


REPORT_CUSTOM = (
    "report it to the author of the 'bla_custom_no_tracker' custom integration"
)
REPORT_CUSTOM_UNKNOWN = "report it to the custom integration author"


@pytest.mark.parametrize(
    ("domain", "module", "report_issue"),
    [
        (None, None, f"create a bug report at {CORE_ISSUE_TRACKER}"),
        ("bla_custom", None, f"create a bug report at {CUSTOM_ISSUE_TRACKER}"),
        ("bla_custom_no_tracker", None, REPORT_CUSTOM),
        (None, "custom_components.hue.sensor", REPORT_CUSTOM_UNKNOWN),
    ],
)
async def test_async_suggest_report_issue(
    hass: HomeAssistant, domain: str | None, module: str | None, report_issue: str
) -> None:
    """Test async_suggest_report_issue."""
    mock_integration(hass, MockModule("bla_built_in"))
    mock_integration(
        hass,
        MockModule(
            "bla_custom", partial_manifest={"issue_tracker": CUSTOM_ISSUE_TRACKER}
        ),
        built_in=False,
    )
    mock_integration(hass, MockModule("bla_custom_no_tracker"), built_in=False)
    assert (
        loader.async_suggest_report_issue(
            hass, integration_domain=domain, module=module
        )
        == report_issue
    )


def test_import_executor_default(hass: HomeAssistant) -> None:
    """Test that import_executor defaults."""
    custom_comp = mock_integration(hass, MockModule("any_random"), built_in=False)
    assert custom_comp.import_executor is True
    built_in_comp = mock_integration(hass, MockModule("other_random"), built_in=True)
    assert built_in_comp.import_executor is True


async def test_config_folder_not_in_path() -> None:
    """Test that config folder is not in path."""

    # Verify that we are unable to import this file from top level
    with pytest.raises(ImportError):
        # pylint: disable-next=import-outside-toplevel
        import check_config_not_in_path  # noqa: F401

    # Verify that we are able to load the file with absolute path
    # pylint: disable-next=import-outside-toplevel,hass-relative-import
    import tests.testing_config.check_config_not_in_path  # noqa: F401


async def test_hass_components_use_reported(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_integration_frame: Mock
) -> None:
    """Test that use of hass.components is reported."""
    mock_integration_frame.filename = (
        "/home/paulus/homeassistant/custom_components/demo/light.py"
    )
    integration_frame = frame.IntegrationFrame(
        custom_integration=True,
        frame=mock_integration_frame,
        integration="test_integration_frame",
        module="custom_components.test_integration_frame",
        relative_filename="custom_components/test_integration_frame/__init__.py",
    )

    with (
        patch(
            "homeassistant.helpers.frame.get_integration_frame",
            return_value=integration_frame,
        ),
        patch(
            "homeassistant.components.http.start_http_server_and_save_config",
            return_value=None,
        ),
    ):
        await hass.components.http.start_http_server_and_save_config(hass, [], None)

        assert (
            "Detected that custom integration 'test_integration_frame'"
            " accesses hass.components.http. This is deprecated"
        ) in caplog.text


async def test_async_get_component_preloads_config_and_config_flow(
    hass: HomeAssistant,
) -> None:
    """Verify async_get_component will try to preload the config and config_flow platform."""
    executor_import_integration = _get_test_integration(
        hass, "executor_import", True, import_executor=True
    )
    assert executor_import_integration.import_executor is True

    assert "homeassistant.components.executor_import" not in sys.modules
    assert "custom_components.executor_import" not in sys.modules

    platform_exists_calls = []

    def mock_platforms_exists(platforms: list[str]) -> bool:
        platform_exists_calls.append(platforms)
        return platforms

    with (
        patch("homeassistant.loader.importlib.import_module") as mock_import,
        patch.object(
            executor_import_integration, "platforms_exists", mock_platforms_exists
        ),
    ):
        await executor_import_integration.async_get_component()

    assert len(platform_exists_calls[0]) == len(loader.BASE_PRELOAD_PLATFORMS)
    assert mock_import.call_count == 1 + len(loader.BASE_PRELOAD_PLATFORMS)
    assert (
        mock_import.call_args_list[0][0][0]
        == "homeassistant.components.executor_import"
    )
    checked_platforms = {
        mock_import.call_args_list[i][0][0]
        for i in range(1, len(mock_import.call_args_list))
    }
    assert checked_platforms == {
        "homeassistant.components.executor_import.config_flow",
        *(
            f"homeassistant.components.executor_import.{platform}"
            for platform in loader.BASE_PRELOAD_PLATFORMS
        ),
    }


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_async_get_component_loads_loop_if_already_in_sys_modules(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify async_get_component does not create an executor job if the module is already in sys.modules."""
    integration = await loader.async_get_integration(
        hass, "test_package_loaded_executor"
    )
    assert integration.pkg_path == "custom_components.test_package_loaded_executor"
    assert integration.import_executor is True
    assert integration.config_flow is True

    assert "test_package_loaded_executor" not in hass.config.components
    assert "test_package_loaded_executor.config_flow" not in hass.config.components

    config_flow_module_name = f"{integration.pkg_path}.config_flow"
    module_mock = MagicMock(__file__="__init__.py")
    config_flow_module_mock = MagicMock(__file__="config_flow.py")

    def import_module(name: str) -> Any:
        if name == integration.pkg_path:
            return module_mock
        if name == config_flow_module_name:
            return config_flow_module_mock
        raise ImportError

    modules_without_config_flow = {
        k: v for k, v in sys.modules.items() if k != config_flow_module_name
    }
    with (
        patch.dict(
            "sys.modules",
            {**modules_without_config_flow, integration.pkg_path: module_mock},
            clear=True,
        ),
        patch("homeassistant.loader.importlib.import_module", import_module),
    ):
        module = await integration.async_get_component()

    # The config flow is missing so we should load
    # in the executor
    assert "loaded_executor=True" in caplog.text
    assert "loaded_executor=False" not in caplog.text
    assert module is module_mock
    caplog.clear()

    with (
        patch.dict(
            "sys.modules",
            {
                integration.pkg_path: module_mock,
                config_flow_module_name: config_flow_module_mock,
            },
        ),
        patch("homeassistant.loader.importlib.import_module", import_module),
    ):
        module = await integration.async_get_component()

    # Everything is already in the integration cache
    # so it should not have to call the load
    assert "loaded_executor" not in caplog.text
    assert module is module_mock


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_async_get_component_concurrent_loads(hass: HomeAssistant) -> None:
    """Verify async_get_component waits if the first load if called again when still in progress."""
    integration = await loader.async_get_integration(
        hass, "test_package_loaded_executor"
    )
    assert integration.pkg_path == "custom_components.test_package_loaded_executor"
    assert integration.import_executor is True
    assert integration.config_flow is True

    assert "test_package_loaded_executor" not in hass.config.components
    assert "test_package_loaded_executor.config_flow" not in hass.config.components

    config_flow_module_name = f"{integration.pkg_path}.config_flow"
    module_mock = MagicMock(__file__="__init__.py")
    config_flow_module_mock = MagicMock(__file__="config_flow.py")
    imports = []
    start_event = threading.Event()
    import_event = asyncio.Event()

    def import_module(name: str) -> Any:
        hass.loop.call_soon_threadsafe(import_event.set)
        imports.append(name)
        start_event.wait()
        if name == integration.pkg_path:
            return module_mock
        if name == config_flow_module_name:
            return config_flow_module_mock
        raise ImportError

    modules_without_integration = {
        k: v
        for k, v in sys.modules.items()
        if k not in (config_flow_module_name, integration.pkg_path)
    }
    with (
        patch.dict(
            "sys.modules",
            {**modules_without_integration},
            clear=True,
        ),
        patch("homeassistant.loader.importlib.import_module", import_module),
    ):
        load_task1 = asyncio.create_task(integration.async_get_component())
        load_task2 = asyncio.create_task(integration.async_get_component())
        await import_event.wait()  # make sure the import is started
        assert not integration._component_future.done()
        start_event.set()
        comp1 = await load_task1
        comp2 = await load_task2
        assert integration._component_future is None

    assert comp1 is module_mock
    assert comp2 is module_mock

    assert integration.pkg_path in imports
    assert config_flow_module_name in imports


async def test_async_get_component_deadlock_fallback(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify async_get_component fallback to importing in the event loop on deadlock."""
    executor_import_integration = _get_test_integration(
        hass, "executor_import", True, import_executor=True
    )
    assert executor_import_integration.import_executor is True
    module_mock = MagicMock(__file__="__init__.py")
    import_attempts = 0

    def mock_import(module: str, *args: Any, **kwargs: Any) -> Any:
        nonlocal import_attempts
        if module == "homeassistant.components.executor_import":
            import_attempts += 1

        if import_attempts == 1:
            # _DeadlockError inherits from RuntimeError
            raise RuntimeError(
                "Detected deadlock trying to import homeassistant.components.executor_import"
            )

        return module_mock

    assert "homeassistant.components.executor_import" not in sys.modules
    assert "custom_components.executor_import" not in sys.modules
    with patch("homeassistant.loader.importlib.import_module", mock_import):
        module = await executor_import_integration.async_get_component()

    assert (
        "Detected deadlock trying to import homeassistant.components.executor_import"
        in caplog.text
    )
    assert "loaded_executor=False" in caplog.text
    assert module is module_mock


async def test_async_get_component_deadlock_fallback_module_not_found(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify async_get_component fallback behavior.

    Ensure that fallback is not triggered on ModuleNotFoundError.
    """
    executor_import_integration = _get_test_integration(
        hass, "executor_import", True, import_executor=True
    )
    assert executor_import_integration.import_executor is True
    module_mock = MagicMock(__file__="__init__.py")
    import_attempts = 0

    def mock_import(module: str, *args: Any, **kwargs: Any) -> Any:
        nonlocal import_attempts
        if module == "homeassistant.components.executor_import":
            import_attempts += 1

        if import_attempts == 1:
            raise ModuleNotFoundError(
                "homeassistant.components.executor_import not found",
                name="homeassistant.components.executor_import",
            )

        return module_mock

    assert "homeassistant.components.executor_import" not in sys.modules
    assert "custom_components.executor_import" not in sys.modules
    with (
        patch("homeassistant.loader.importlib.import_module", mock_import),
        pytest.raises(
            ModuleNotFoundError, match="homeassistant.components.executor_import"
        ),
    ):
        await executor_import_integration.async_get_component()

    # We should not have tried to fall back to the event loop import
    assert "loaded_executor=False" not in caplog.text
    assert "homeassistant.components.executor_import" not in sys.modules
    assert "custom_components.executor_import" not in sys.modules
    assert import_attempts == 1


async def test_async_get_component_raises_after_import_failure(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify async_get_component raises if we fail to import in both the executor and loop."""
    executor_import_integration = _get_test_integration(
        hass, "executor_import", True, import_executor=True
    )
    assert executor_import_integration.import_executor is True
    module_mock = MagicMock()
    import_attempts = 0

    def mock_import(module: str, *args: Any, **kwargs: Any) -> Any:
        nonlocal import_attempts
        if module == "homeassistant.components.executor_import":
            import_attempts += 1

        if import_attempts == 1:
            # _DeadlockError inherits from RuntimeError
            raise RuntimeError(
                "Detected deadlock trying to import homeassistant.components.executor_import"
            )

        if import_attempts == 2:
            raise ImportError("Failed import homeassistant.components.executor_import")
        return module_mock

    assert "homeassistant.components.executor_import" not in sys.modules
    assert "custom_components.executor_import" not in sys.modules
    with (
        patch("homeassistant.loader.importlib.import_module", mock_import),
        pytest.raises(ImportError),
    ):
        await executor_import_integration.async_get_component()

    assert (
        "Detected deadlock trying to import homeassistant.components.executor_import"
        in caplog.text
    )
    assert "loaded_executor=False" not in caplog.text


async def test_async_get_platform_deadlock_fallback(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify async_get_platform fallback to importing in the event loop on deadlock."""
    executor_import_integration = _get_test_integration(
        hass, "executor_import", True, import_executor=True
    )
    assert executor_import_integration.import_executor is True
    module_mock = MagicMock()
    import_attempts = 0

    def mock_import(module: str, *args: Any, **kwargs: Any) -> Any:
        nonlocal import_attempts
        if module == "homeassistant.components.executor_import.config_flow":
            import_attempts += 1

        if import_attempts == 1:
            # _DeadlockError inherits from RuntimeError
            raise RuntimeError(
                "Detected deadlock trying to import homeassistant.components.executor_import"
            )

        return module_mock

    assert "homeassistant.components.executor_import" not in sys.modules
    assert "custom_components.executor_import" not in sys.modules
    with patch("homeassistant.loader.importlib.import_module", mock_import):
        module = await executor_import_integration.async_get_platform("config_flow")

    assert (
        "Detected deadlock trying to import homeassistant.components.executor_import"
        in caplog.text
    )
    # We should have tried both the executor and loop
    assert "executor=['config_flow']" in caplog.text
    assert "loop=['config_flow']" in caplog.text
    assert module is module_mock


async def test_async_get_platform_deadlock_fallback_module_not_found(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify async_get_platform fallback behavior.

    Ensure that fallback is not triggered on ModuleNotFoundError.
    """
    executor_import_integration = _get_test_integration(
        hass, "executor_import", True, import_executor=True
    )
    assert executor_import_integration.import_executor is True
    module_mock = MagicMock()
    import_attempts = 0

    def mock_import(module: str, *args: Any, **kwargs: Any) -> Any:
        nonlocal import_attempts
        if module == "homeassistant.components.executor_import.config_flow":
            import_attempts += 1

        if import_attempts == 1:
            raise ModuleNotFoundError(
                "Not found homeassistant.components.executor_import.config_flow",
                name="homeassistant.components.executor_import.config_flow",
            )

        return module_mock

    assert "homeassistant.components.executor_import" not in sys.modules
    assert "custom_components.executor_import" not in sys.modules
    with (
        patch("homeassistant.loader.importlib.import_module", mock_import),
        pytest.raises(
            ModuleNotFoundError,
            match="homeassistant.components.executor_import.config_flow",
        ),
    ):
        await executor_import_integration.async_get_platform("config_flow")

    # We should not have tried to fall back to the event loop import
    assert "executor=['config_flow']" in caplog.text
    assert "loop=['config_flow']" not in caplog.text
    assert "homeassistant.components.executor_import" not in sys.modules
    assert "custom_components.executor_import" not in sys.modules
    assert import_attempts == 1


async def test_async_get_platform_raises_after_import_failure(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify async_get_platform raises if we fail to import in both the executor and loop."""
    executor_import_integration = _get_test_integration(
        hass, "executor_import", True, import_executor=True
    )
    assert executor_import_integration.import_executor is True
    module_mock = MagicMock()
    import_attempts = 0

    def mock_import(module: str, *args: Any, **kwargs: Any) -> Any:
        nonlocal import_attempts
        if module == "homeassistant.components.executor_import.config_flow":
            import_attempts += 1

        if import_attempts == 1:
            # _DeadlockError inherits from RuntimeError
            raise RuntimeError(
                "Detected deadlock trying to import homeassistant.components.executor_import"
            )

        if import_attempts == 2:
            # _DeadlockError inherits from RuntimeError
            raise ImportError(
                "Error trying to import homeassistant.components.executor_import"
            )

        return module_mock

    assert "homeassistant.components.executor_import" not in sys.modules
    assert "custom_components.executor_import" not in sys.modules
    with (
        patch("homeassistant.loader.importlib.import_module", mock_import),
        pytest.raises(ImportError),
    ):
        await executor_import_integration.async_get_platform("config_flow")

    assert (
        "Detected deadlock trying to import homeassistant.components.executor_import"
        in caplog.text
    )
    assert "loaded_executor=False" not in caplog.text


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_platforms_exists(hass: HomeAssistant) -> None:
    """Test platforms_exists."""
    original_os_listdir = os.listdir

    paths: list[str] = []

    def mock_list_dir(path: str) -> list[str]:
        paths.append(path)
        return original_os_listdir(path)

    with patch("homeassistant.loader.os.listdir", mock_list_dir):
        integration = await loader.async_get_integration(
            hass, "test_integration_platform"
        )
        assert integration.domain == "test_integration_platform"

    # Verify the files cache is primed
    assert integration.file_path in paths

    # component is loaded, should now return False
    with patch("homeassistant.loader.os.listdir", wraps=os.listdir) as mock_exists:
        component = integration.get_component()
    assert component.DOMAIN == "test_integration_platform"

    # The files cache should be primed when
    # the integration is resolved
    assert mock_exists.call_count == 0

    # component is loaded, should now return False
    with patch("homeassistant.loader.os.listdir", wraps=os.listdir) as mock_exists:
        assert integration.platforms_exists(("non_existing",)) == []

    # We should remember which files exist
    assert mock_exists.call_count == 0

    # component is loaded, should now return False
    with patch("homeassistant.loader.os.listdir", wraps=os.listdir) as mock_exists:
        assert integration.platforms_exists(("non_existing",)) == []

    # We should remember the file does not exist
    assert mock_exists.call_count == 0

    assert integration.platforms_exists(["group"]) == ["group"]

    platform = await integration.async_get_platform("group")
    assert platform.MAGIC == 1

    platform = integration.get_platform("group")
    assert platform.MAGIC == 1

    assert integration.platforms_exists(["group"]) == ["group"]

    assert integration.platforms_are_loaded(["group"]) is True
    assert integration.platforms_are_loaded(["other"]) is False


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_async_get_platforms_loads_loop_if_already_in_sys_modules(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify async_get_platforms does not create an executor job.

    Case is for when the module is already in sys.modules.
    """
    integration = await loader.async_get_integration(
        hass, "test_package_loaded_executor"
    )
    assert integration.pkg_path == "custom_components.test_package_loaded_executor"
    assert integration.import_executor is True
    assert integration.config_flow is True

    assert "test_package_loaded_executor" not in hass.config.components
    assert "test_package_loaded_executor.config_flow" not in hass.config.components
    await integration.async_get_component()

    button_module_name = f"{integration.pkg_path}.button"
    switch_module_name = f"{integration.pkg_path}.switch"
    light_module_name = f"{integration.pkg_path}.light"
    button_module_mock = MagicMock()
    switch_module_mock = MagicMock()
    light_module_mock = MagicMock()

    def import_module(name: str) -> Any:
        if name == button_module_name:
            return button_module_mock
        if name == switch_module_name:
            return switch_module_mock
        if name == light_module_name:
            return light_module_mock
        raise ImportError

    modules_without_button = {
        k: v for k, v in sys.modules.items() if k != button_module_name
    }
    with (
        patch.dict(
            "sys.modules",
            modules_without_button,
            clear=True,
        ),
        patch("homeassistant.loader.importlib.import_module", import_module),
    ):
        module = (await integration.async_get_platforms(["button"]))["button"]

    # The button module is missing so we should load
    # in the executor
    assert "executor=['button']" in caplog.text
    assert "loop=[]" in caplog.text
    assert module is button_module_mock
    caplog.clear()

    with (
        patch.dict(
            "sys.modules",
            {
                **modules_without_button,
                button_module_name: button_module_mock,
            },
        ),
        patch("homeassistant.loader.importlib.import_module", import_module),
    ):
        module = (await integration.async_get_platforms(["button"]))["button"]

    # Everything is cached so there should be no logging
    assert "loop=" not in caplog.text
    assert "executor=" not in caplog.text
    assert module is button_module_mock
    caplog.clear()

    modules_without_switch = {
        k: v for k, v in sys.modules.items() if k not in switch_module_name
    }
    with (
        patch.dict(
            "sys.modules",
            {**modules_without_switch, light_module_name: light_module_mock},
            clear=True,
        ),
        patch("homeassistant.loader.importlib.import_module", import_module),
    ):
        modules = await integration.async_get_platforms(["button", "switch", "light"])

    # The button module is already in the cache so nothing happens
    # The switch module is loaded in the executor since its not in the cache
    # The light module is in memory but not in the cache so its loaded in the loop
    assert "['button']" not in caplog.text
    assert "executor=['switch']" in caplog.text
    assert "loop=['light']" in caplog.text
    assert modules == {
        "button": button_module_mock,
        "switch": switch_module_mock,
        "light": light_module_mock,
    }
    assert integration.get_platform_cached("button") is button_module_mock
    assert integration.get_platform_cached("switch") is switch_module_mock
    assert integration.get_platform_cached("light") is light_module_mock


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_async_get_platforms_concurrent_loads(hass: HomeAssistant) -> None:
    """Verify async_get_platforms waits if the first load if called again.

    Case is for when when a second load is called
    and the first is still in progress.
    """
    integration = await loader.async_get_integration(
        hass, "test_package_loaded_executor"
    )
    assert integration.pkg_path == "custom_components.test_package_loaded_executor"
    assert integration.import_executor is True
    assert integration.config_flow is True

    assert "test_package_loaded_executor" not in hass.config.components
    assert "test_package_loaded_executor.config_flow" not in hass.config.components
    await integration.async_get_component()

    button_module_name = f"{integration.pkg_path}.button"
    button_module_mock = MagicMock()

    imports = []
    start_event = threading.Event()
    import_event = asyncio.Event()

    def import_module(name: str) -> Any:
        hass.loop.call_soon_threadsafe(import_event.set)
        imports.append(name)
        start_event.wait()
        if name == button_module_name:
            return button_module_mock
        raise ImportError

    modules_without_button = {
        k: v
        for k, v in sys.modules.items()
        if k not in (button_module_name, integration.pkg_path)
    }
    with (
        patch.dict(
            "sys.modules",
            modules_without_button,
            clear=True,
        ),
        patch("homeassistant.loader.importlib.import_module", import_module),
    ):
        load_task1 = asyncio.create_task(integration.async_get_platforms(["button"]))
        load_task2 = asyncio.create_task(integration.async_get_platforms(["button"]))
        await import_event.wait()  # make sure the import is started
        assert not integration._import_futures["button"].done()
        start_event.set()
        load_result1 = await load_task1
        load_result2 = await load_task2
        assert integration._import_futures is not None

    assert load_result1 == {"button": button_module_mock}
    assert load_result2 == {"button": button_module_mock}

    assert imports == [button_module_name]
    assert integration.get_platform_cached("button") is button_module_mock


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_integration_warnings(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test integration warnings."""
    await loader.async_get_integration(hass, "test_package_loaded_loop")
    assert "configured to to import its code in the event loop" in caplog.text


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_has_services(hass: HomeAssistant) -> None:
    """Test has_services."""
    integration = await loader.async_get_integration(hass, "test")
    assert integration.has_services is False
    integration = await loader.async_get_integration(hass, "test_with_services")
    assert integration.has_services is True


async def test_hass_helpers_use_reported(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_integration_frame: Mock
) -> None:
    """Test that use of hass.components is reported."""
    integration_frame = frame.IntegrationFrame(
        custom_integration=True,
        frame=mock_integration_frame,
        integration="test_integration_frame",
        module="custom_components.test_integration_frame",
        relative_filename="custom_components/test_integration_frame/__init__.py",
    )

    with (
        patch.object(frame, "_REPORTED_INTEGRATIONS", new=set()),
        patch(
            "homeassistant.helpers.frame.get_integration_frame",
            return_value=integration_frame,
        ),
        patch(
            "homeassistant.helpers.aiohttp_client.async_get_clientsession",
            return_value=None,
        ),
    ):
        hass.helpers.aiohttp_client.async_get_clientsession()

        assert (
            "Detected that custom integration 'test_integration_frame' "
            "accesses hass.helpers.aiohttp_client. This is deprecated"
        ) in caplog.text


async def test_manifest_json_fragment_round_trip(hass: HomeAssistant) -> None:
    """Test json_fragment roundtrip."""
    integration = await loader.async_get_integration(hass, "hue")
    assert (
        json_loads(json_dumps(integration.manifest_json_fragment))
        == integration.manifest
    )
