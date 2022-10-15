"""Test to verify that we can load components."""
from unittest.mock import patch

import pytest

from homeassistant import core, loader
from homeassistant.components import http, hue
from homeassistant.components.hue import light as hue_light

from tests.common import MockModule, mock_integration


async def test_component_dependencies(hass):
    """Test if we can get the proper load order of components."""
    mock_integration(hass, MockModule("mod1"))
    mock_integration(hass, MockModule("mod2", ["mod1"]))
    mod_3 = mock_integration(hass, MockModule("mod3", ["mod2"]))

    assert {"mod1", "mod2", "mod3"} == await loader._async_component_dependencies(
        hass, "mod_3", mod_3, set(), set()
    )

    # Create circular dependency
    mock_integration(hass, MockModule("mod1", ["mod3"]))

    with pytest.raises(loader.CircularDependency):
        print(
            await loader._async_component_dependencies(
                hass, "mod_3", mod_3, set(), set()
            )
        )

    # Depend on non-existing component
    mod_1 = mock_integration(hass, MockModule("mod1", ["nonexisting"]))

    with pytest.raises(loader.IntegrationNotFound):
        print(
            await loader._async_component_dependencies(
                hass, "mod_1", mod_1, set(), set()
            )
        )

    # Having an after dependency 2 deps down that is circular
    mod_1 = mock_integration(
        hass, MockModule("mod1", partial_manifest={"after_dependencies": ["mod_3"]})
    )

    with pytest.raises(loader.CircularDependency):
        print(
            await loader._async_component_dependencies(
                hass, "mod_3", mod_3, set(), set()
            )
        )


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
    components = loader.Components(hass)
    components.persistent_notification.async_create("message")

    assert len(hass.states.async_entity_ids("persistent_notification")) == 1


async def test_helpers_wrapper(hass):
    """Test helpers wrapper."""
    helpers = loader.Helpers(hass)

    result = []

    @core.callback
    def discovery_callback(service, discovered):
        """Handle discovery callback."""
        result.append(discovered)

    helpers.discovery.async_listen("service_name", discovery_callback)

    await helpers.discovery.async_discover("service_name", "hello", None, {})
    await hass.async_block_till_done()

    assert result == ["hello"]


async def test_custom_component_name(hass, enable_custom_integrations):
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
    assert platform.__name__ == "custom_components.test.light"
    assert platform.__package__ == "custom_components.test"

    # Test custom components is mounted
    from custom_components.test_package import TEST

    assert TEST == 5


async def test_log_warning_custom_component(hass, caplog, enable_custom_integrations):
    """Test that we log a warning when loading a custom component."""

    await loader.async_get_integration(hass, "test_package")
    assert "We found a custom integration test_package" in caplog.text

    await loader.async_get_integration(hass, "test")
    assert "We found a custom integration test " in caplog.text


async def test_custom_integration_version_not_valid(
    hass, caplog, enable_custom_integrations
):
    """Test that we log a warning when custom integrations have a invalid version."""
    with pytest.raises(loader.IntegrationNotFound):
        await loader.async_get_integration(hass, "test_no_version")

    assert (
        "The custom integration 'test_no_version' does not have a version key in the manifest file and was blocked from loading."
        in caplog.text
    )

    with pytest.raises(loader.IntegrationNotFound):
        await loader.async_get_integration(hass, "test2")
    assert (
        "The custom integration 'test_bad_version' does not have a valid version key (bad) in the manifest file and was blocked from loading."
        in caplog.text
    )


async def test_get_integration(hass):
    """Test resolving integration."""
    integration = await loader.async_get_integration(hass, "hue")
    assert hue == integration.get_component()
    assert hue_light == integration.get_platform("light")


async def test_get_integration_exceptions(hass):
    """Test resolving integration."""
    integration = await loader.async_get_integration(hass, "hue")

    with pytest.raises(ImportError), patch(
        "homeassistant.loader.importlib.import_module", side_effect=ValueError("Boom")
    ):
        assert hue == integration.get_component()

    with pytest.raises(ImportError), patch(
        "homeassistant.loader.importlib.import_module", side_effect=ValueError("Boom")
    ):
        assert hue_light == integration.get_platform("light")


async def test_get_integration_legacy(hass, enable_custom_integrations):
    """Test resolving integration."""
    integration = await loader.async_get_integration(hass, "test_embedded")
    assert integration.get_component().DOMAIN == "test_embedded"
    assert integration.get_platform("switch") is not None


async def test_get_integration_custom_component(hass, enable_custom_integrations):
    """Test resolving integration."""
    integration = await loader.async_get_integration(hass, "test_package")
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


async def test_integrations_only_once(hass):
    """Test that we load integrations only once."""
    int_1 = hass.async_create_task(loader.async_get_integration(hass, "hue"))
    int_2 = hass.async_create_task(loader.async_get_integration(hass, "hue"))

    assert await int_1 is await int_2


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
            "zeroconf": [f"_{name}._tcp.local."],
            "homekit": {"models": [name]},
            "ssdp": [{"manufacturer": name, "modelName": name}],
            "mqtt": [f"{name}/discovery"],
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


async def test_get_custom_components(hass, enable_custom_integrations):
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


async def test_get_zeroconf(hass):
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


async def test_get_application_credentials(hass):
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


async def test_get_zeroconf_back_compat(hass):
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


async def test_get_bluetooth(hass):
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


async def test_get_dhcp(hass):
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


async def test_get_usb(hass):
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


async def test_get_homekit(hass):
    """Verify that custom components with homekit are found."""
    test_1_integration = _get_test_integration(hass, "test_1", True)
    test_2_integration = _get_test_integration(hass, "test_2", True)

    with patch("homeassistant.loader.async_get_custom_components") as mock_get:
        mock_get.return_value = {
            "test_1": test_1_integration,
            "test_2": test_2_integration,
        }
        homekit = await loader.async_get_homekit(hass)
        assert homekit["test_1"] == "test_1"
        assert homekit["test_2"] == "test_2"


async def test_get_ssdp(hass):
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


async def test_get_mqtt(hass):
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


async def test_get_custom_components_safe_mode(hass):
    """Test that we get empty custom components in safe mode."""
    hass.config.safe_mode = True
    assert await loader.async_get_custom_components(hass) == {}


async def test_custom_integration_missing_version(hass, caplog):
    """Test trying to load a custom integration without a version twice does not deadlock."""
    with pytest.raises(loader.IntegrationNotFound):
        await loader.async_get_integration(hass, "test_no_version")

    with pytest.raises(loader.IntegrationNotFound):
        await loader.async_get_integration(hass, "test_no_version")


async def test_custom_integration_missing(hass, caplog):
    """Test trying to load a custom integration that is missing twice not deadlock."""
    with patch("homeassistant.loader.async_get_custom_components") as mock_get:
        mock_get.return_value = {}

        with pytest.raises(loader.IntegrationNotFound):
            await loader.async_get_integration(hass, "test1")

        with pytest.raises(loader.IntegrationNotFound):
            await loader.async_get_integration(hass, "test1")


async def test_validation(hass):
    """Test we raise if invalid domain passed in."""
    with pytest.raises(ValueError):
        await loader.async_get_integration(hass, "some.thing")


async def test_loggers(hass):
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
