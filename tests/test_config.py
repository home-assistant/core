"""Test config utils."""

import asyncio
from collections import OrderedDict
import contextlib
import copy
import logging
import os
from typing import Any
from unittest import mock
from unittest.mock import AsyncMock, Mock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol
from voluptuous import Invalid, MultipleInvalid
import yaml

from homeassistant import config, loader
import homeassistant.config as config_util
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_FRIENDLY_NAME,
    CONF_AUTH_MFA_MODULES,
    CONF_AUTH_PROVIDERS,
    CONF_CUSTOMIZE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
    __version__,
)
from homeassistant.core import (
    DOMAIN as HA_DOMAIN,
    ConfigSource,
    HomeAssistant,
    HomeAssistantError,
)
from homeassistant.exceptions import ConfigValidationError
from homeassistant.helpers import (
    check_config,
    config_validation as cv,
    issue_registry as ir,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import Integration, async_get_integration
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import (
    _CONF_UNIT_SYSTEM_US_CUSTOMARY,
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)
from homeassistant.util.yaml import SECRET_YAML
from homeassistant.util.yaml.objects import NodeDictClass

from .common import (
    MockModule,
    MockPlatform,
    MockUser,
    get_test_config_dir,
    mock_integration,
    mock_platform,
)

CONFIG_DIR = get_test_config_dir()
YAML_PATH = os.path.join(CONFIG_DIR, config_util.YAML_CONFIG_FILE)
SECRET_PATH = os.path.join(CONFIG_DIR, SECRET_YAML)
VERSION_PATH = os.path.join(CONFIG_DIR, config_util.VERSION_FILE)
AUTOMATIONS_PATH = os.path.join(CONFIG_DIR, config_util.AUTOMATION_CONFIG_PATH)
SCRIPTS_PATH = os.path.join(CONFIG_DIR, config_util.SCRIPT_CONFIG_PATH)
SCENES_PATH = os.path.join(CONFIG_DIR, config_util.SCENE_CONFIG_PATH)
SAFE_MODE_PATH = os.path.join(CONFIG_DIR, config_util.SAFE_MODE_FILENAME)


def create_file(path):
    """Create an empty file."""
    with open(path, "w"):
        pass


@pytest.fixture(autouse=True)
def teardown():
    """Clean up."""
    yield

    if os.path.isfile(YAML_PATH):
        os.remove(YAML_PATH)

    if os.path.isfile(SECRET_PATH):
        os.remove(SECRET_PATH)

    if os.path.isfile(VERSION_PATH):
        os.remove(VERSION_PATH)

    if os.path.isfile(AUTOMATIONS_PATH):
        os.remove(AUTOMATIONS_PATH)

    if os.path.isfile(SCRIPTS_PATH):
        os.remove(SCRIPTS_PATH)

    if os.path.isfile(SCENES_PATH):
        os.remove(SCENES_PATH)

    if os.path.isfile(SAFE_MODE_PATH):
        os.remove(SAFE_MODE_PATH)


IOT_DOMAIN_PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({vol.Remove("old"): str})


@pytest.fixture
async def mock_iot_domain_integration(hass: HomeAssistant) -> Integration:
    """Mock an integration which provides an IoT domain."""
    comp_platform_schema = cv.PLATFORM_SCHEMA.extend({vol.Remove("old"): str})
    comp_platform_schema_base = comp_platform_schema.extend({}, extra=vol.ALLOW_EXTRA)

    return mock_integration(
        hass,
        MockModule(
            "iot_domain",
            platform_schema_base=comp_platform_schema_base,
            platform_schema=comp_platform_schema,
        ),
    )


@pytest.fixture
async def mock_iot_domain_integration_with_docs(hass: HomeAssistant) -> Integration:
    """Mock an integration which provides an IoT domain."""
    comp_platform_schema = cv.PLATFORM_SCHEMA.extend({vol.Remove("old"): str})
    comp_platform_schema_base = comp_platform_schema.extend({}, extra=vol.ALLOW_EXTRA)

    return mock_integration(
        hass,
        MockModule(
            "iot_domain",
            platform_schema_base=comp_platform_schema_base,
            platform_schema=comp_platform_schema,
            partial_manifest={
                "documentation": "https://www.home-assistant.io/integrations/iot_domain"
            },
        ),
    )


@pytest.fixture
async def mock_non_adr_0007_integration(hass: HomeAssistant) -> None:
    """Mock a non-ADR-0007 compliant integration with iot_domain platform.

    The integration allows setting up iot_domain entities under the iot_domain's
    configuration key
    """

    test_platform_schema = IOT_DOMAIN_PLATFORM_SCHEMA.extend(
        {vol.Required("option1"): str, vol.Optional("option2"): str}
    )
    mock_platform(
        hass,
        "non_adr_0007.iot_domain",
        MockPlatform(platform_schema=test_platform_schema),
    )


@pytest.fixture
async def mock_non_adr_0007_integration_with_docs(hass: HomeAssistant) -> None:
    """Mock a non-ADR-0007 compliant integration with iot_domain platform.

    The integration allows setting up iot_domain entities under the iot_domain's
    configuration key
    """

    mock_integration(
        hass,
        MockModule(
            "non_adr_0007",
            partial_manifest={
                "documentation": "https://www.home-assistant.io/integrations/non_adr_0007"
            },
        ),
    )
    test_platform_schema = IOT_DOMAIN_PLATFORM_SCHEMA.extend(
        {vol.Required("option1"): str, vol.Optional("option2"): str}
    )
    mock_platform(
        hass,
        "non_adr_0007.iot_domain",
        MockPlatform(platform_schema=test_platform_schema),
    )


@pytest.fixture
async def mock_adr_0007_integrations(hass: HomeAssistant) -> list[Integration]:
    """Mock ADR-0007 compliant integrations."""
    integrations = []
    for domain in [
        "adr_0007_1",
        "adr_0007_2",
        "adr_0007_3",
        "adr_0007_4",
        "adr_0007_5",
    ]:
        adr_0007_config_schema = vol.Schema(
            {
                domain: vol.Schema(
                    {
                        vol.Required("host"): str,
                        vol.Optional("port", default=8080): int,
                    }
                )
            },
            extra=vol.ALLOW_EXTRA,
        )
        integrations.append(
            mock_integration(
                hass,
                MockModule(domain, config_schema=adr_0007_config_schema),
            )
        )
    return integrations


@pytest.fixture
async def mock_adr_0007_integrations_with_docs(
    hass: HomeAssistant,
) -> list[Integration]:
    """Mock ADR-0007 compliant integrations."""
    integrations = []
    for domain in [
        "adr_0007_1",
        "adr_0007_2",
        "adr_0007_3",
        "adr_0007_4",
        "adr_0007_5",
    ]:
        adr_0007_config_schema = vol.Schema(
            {
                domain: vol.Schema(
                    {
                        vol.Required("host"): str,
                        vol.Optional("port", default=8080): int,
                    }
                )
            },
            extra=vol.ALLOW_EXTRA,
        )
        integrations.append(
            mock_integration(
                hass,
                MockModule(
                    domain,
                    config_schema=adr_0007_config_schema,
                    partial_manifest={
                        "documentation": f"https://www.home-assistant.io/integrations/{domain}"
                    },
                ),
            )
        )
    return integrations


@pytest.fixture
async def mock_custom_validator_integrations(hass: HomeAssistant) -> list[Integration]:
    """Mock integrations with custom validator."""
    integrations = []

    for domain in ("custom_validator_ok_1", "custom_validator_ok_2"):

        def gen_async_validate_config(domain):
            schema = vol.Schema(
                {
                    domain: vol.Schema(
                        {
                            vol.Required("host"): str,
                            vol.Optional("port", default=8080): int,
                        }
                    )
                },
                extra=vol.ALLOW_EXTRA,
            )

            async def async_validate_config(
                hass: HomeAssistant, config: ConfigType
            ) -> ConfigType:
                """Validate config."""
                return schema(config)

            return async_validate_config

        integrations.append(mock_integration(hass, MockModule(domain)))
        mock_platform(
            hass,
            f"{domain}.config",
            Mock(async_validate_config=gen_async_validate_config(domain)),
        )

    for domain, exception in [
        ("custom_validator_bad_1", HomeAssistantError("broken")),
        ("custom_validator_bad_2", ValueError("broken")),
    ]:
        integrations.append(mock_integration(hass, MockModule(domain)))
        mock_platform(
            hass,
            f"{domain}.config",
            Mock(async_validate_config=AsyncMock(side_effect=exception)),
        )


@pytest.fixture
async def mock_custom_validator_integrations_with_docs(
    hass: HomeAssistant,
) -> list[Integration]:
    """Mock integrations with custom validator."""
    integrations = []

    for domain in ("custom_validator_ok_1", "custom_validator_ok_2"):

        def gen_async_validate_config(domain):
            schema = vol.Schema(
                {
                    domain: vol.Schema(
                        {
                            vol.Required("host"): str,
                            vol.Optional("port", default=8080): int,
                        }
                    )
                },
                extra=vol.ALLOW_EXTRA,
            )

            async def async_validate_config(
                hass: HomeAssistant, config: ConfigType
            ) -> ConfigType:
                """Validate config."""
                return schema(config)

            return async_validate_config

        integrations.append(
            mock_integration(
                hass,
                MockModule(
                    domain,
                    partial_manifest={
                        "documentation": f"https://www.home-assistant.io/integrations/{domain}"
                    },
                ),
            )
        )
        mock_platform(
            hass,
            f"{domain}.config",
            Mock(async_validate_config=gen_async_validate_config(domain)),
        )

    for domain, exception in [
        ("custom_validator_bad_1", HomeAssistantError("broken")),
        ("custom_validator_bad_2", ValueError("broken")),
    ]:
        integrations.append(
            mock_integration(
                hass,
                MockModule(
                    domain,
                    partial_manifest={
                        "documentation": f"https://www.home-assistant.io/integrations/{domain}"
                    },
                ),
            )
        )
        mock_platform(
            hass,
            f"{domain}.config",
            Mock(async_validate_config=AsyncMock(side_effect=exception)),
        )


class ConfigTestClass(NodeDictClass):
    """Test class for config with wrapper."""

    __line__ = 140
    __config_file__ = "configuration.yaml"


async def test_create_default_config(hass: HomeAssistant) -> None:
    """Test creation of default config."""
    assert not os.path.isfile(YAML_PATH)
    assert not os.path.isfile(SECRET_PATH)
    assert not os.path.isfile(VERSION_PATH)
    assert not os.path.isfile(AUTOMATIONS_PATH)

    await config_util.async_create_default_config(hass)

    assert os.path.isfile(YAML_PATH)
    assert os.path.isfile(SECRET_PATH)
    assert os.path.isfile(VERSION_PATH)
    assert os.path.isfile(AUTOMATIONS_PATH)


async def test_ensure_config_exists_creates_config(hass: HomeAssistant) -> None:
    """Test that calling ensure_config_exists.

    If not creates a new config file.
    """
    assert not os.path.isfile(YAML_PATH)
    with patch("builtins.print") as mock_print:
        await config_util.async_ensure_config_exists(hass)

    assert os.path.isfile(YAML_PATH)
    assert mock_print.called


async def test_ensure_config_exists_uses_existing_config(hass: HomeAssistant) -> None:
    """Test that calling ensure_config_exists uses existing config."""
    create_file(YAML_PATH)
    await config_util.async_ensure_config_exists(hass)

    with open(YAML_PATH) as fp:
        content = fp.read()

    # File created with create_file are empty
    assert content == ""


async def test_ensure_existing_files_is_not_overwritten(hass: HomeAssistant) -> None:
    """Test that calling async_create_default_config does not overwrite existing files."""
    create_file(SECRET_PATH)

    await config_util.async_create_default_config(hass)

    with open(SECRET_PATH) as fp:
        content = fp.read()

    # File created with create_file are empty
    assert content == ""


def test_load_yaml_config_converts_empty_files_to_dict() -> None:
    """Test that loading an empty file returns an empty dict."""
    create_file(YAML_PATH)

    assert isinstance(config_util.load_yaml_config_file(YAML_PATH), dict)


def test_load_yaml_config_raises_error_if_not_dict() -> None:
    """Test error raised when YAML file is not a dict."""
    with open(YAML_PATH, "w") as fp:
        fp.write("5")

    with pytest.raises(HomeAssistantError):
        config_util.load_yaml_config_file(YAML_PATH)


def test_load_yaml_config_raises_error_if_malformed_yaml() -> None:
    """Test error raised if invalid YAML."""
    with open(YAML_PATH, "w") as fp:
        fp.write(":-")

    with pytest.raises(HomeAssistantError):
        config_util.load_yaml_config_file(YAML_PATH)


def test_load_yaml_config_raises_error_if_unsafe_yaml() -> None:
    """Test error raised if unsafe YAML."""
    with open(YAML_PATH, "w") as fp:
        fp.write("- !!python/object/apply:os.system []")

    with (
        patch.object(os, "system") as system_mock,
        contextlib.suppress(HomeAssistantError),
    ):
        config_util.load_yaml_config_file(YAML_PATH)

    assert len(system_mock.mock_calls) == 0

    # Here we validate that the test above is a good test
    # since previously the syntax was not valid
    with open(YAML_PATH) as fp, patch.object(os, "system") as system_mock:
        list(yaml.unsafe_load_all(fp))

    assert len(system_mock.mock_calls) == 1


def test_load_yaml_config_preserves_key_order() -> None:
    """Test removal of library."""
    with open(YAML_PATH, "w") as fp:
        fp.write("hello: 2\n")
        fp.write("world: 1\n")

    assert [("hello", 2), ("world", 1)] == list(
        config_util.load_yaml_config_file(YAML_PATH).items()
    )


async def test_create_default_config_returns_none_if_write_error(
    hass: HomeAssistant,
) -> None:
    """Test the writing of a default configuration.

    Non existing folder returns None.
    """
    hass.config.config_dir = os.path.join(CONFIG_DIR, "non_existing_dir/")
    with patch("builtins.print") as mock_print:
        assert await config_util.async_create_default_config(hass) is False
    assert mock_print.called


def test_core_config_schema() -> None:
    """Test core config schema."""
    for value in (
        {CONF_UNIT_SYSTEM: "K"},
        {"time_zone": "non-exist"},
        {"latitude": "91"},
        {"longitude": -181},
        {"external_url": "not an url"},
        {"internal_url": "not an url"},
        {"currency", 100},
        {"customize": "bla"},
        {"customize": {"light.sensor": 100}},
        {"customize": {"entity_id": []}},
        {"country": "xx"},
        {"language": "xx"},
    ):
        with pytest.raises(MultipleInvalid):
            config_util.CORE_CONFIG_SCHEMA(value)

    config_util.CORE_CONFIG_SCHEMA(
        {
            "name": "Test name",
            "latitude": "-23.45",
            "longitude": "123.45",
            "external_url": "https://www.example.com",
            "internal_url": "http://example.local",
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
            "currency": "USD",
            "customize": {"sensor.temperature": {"hidden": True}},
            "country": "SE",
            "language": "sv",
        }
    )


def test_core_config_schema_internal_external_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that we warn for internal/external URL with path."""
    config_util.CORE_CONFIG_SCHEMA(
        {
            "external_url": "https://www.example.com/bla",
            "internal_url": "http://example.local/yo",
        }
    )

    assert "Invalid external_url set" in caplog.text
    assert "Invalid internal_url set" in caplog.text


def test_customize_dict_schema() -> None:
    """Test basic customize config validation."""
    values = ({ATTR_FRIENDLY_NAME: None}, {ATTR_ASSUMED_STATE: "2"})

    for val in values:
        with pytest.raises(MultipleInvalid):
            config_util.CUSTOMIZE_DICT_SCHEMA(val)

    assert config_util.CUSTOMIZE_DICT_SCHEMA(
        {ATTR_FRIENDLY_NAME: 2, ATTR_ASSUMED_STATE: "0"}
    ) == {ATTR_FRIENDLY_NAME: "2", ATTR_ASSUMED_STATE: False}


def test_customize_glob_is_ordered() -> None:
    """Test that customize_glob preserves order."""
    conf = config_util.CORE_CONFIG_SCHEMA({"customize_glob": OrderedDict()})
    assert isinstance(conf["customize_glob"], OrderedDict)


async def _compute_state(hass, config):
    await config_util.async_process_ha_core_config(hass, config)

    entity = Entity()
    entity.entity_id = "test.test"
    entity.hass = hass
    entity.schedule_update_ha_state()

    await hass.async_block_till_done()

    return hass.states.get("test.test")


async def test_entity_customization(hass: HomeAssistant) -> None:
    """Test entity customization through configuration."""
    config = {
        CONF_LATITUDE: 50,
        CONF_LONGITUDE: 50,
        CONF_NAME: "Test",
        CONF_CUSTOMIZE: {"test.test": {"hidden": True}},
    }

    state = await _compute_state(hass, config)

    assert state.attributes["hidden"]


@patch("homeassistant.config.shutil")
@patch("homeassistant.config.os")
@patch("homeassistant.config.is_docker_env", return_value=False)
def test_remove_lib_on_upgrade(
    mock_docker, mock_os, mock_shutil, hass: HomeAssistant
) -> None:
    """Test removal of library on upgrade from before 0.50."""
    ha_version = "0.49.0"
    mock_os.path.isdir = mock.Mock(return_value=True)
    mock_open = mock.mock_open()
    with patch("homeassistant.config.open", mock_open, create=True):
        opened_file = mock_open.return_value
        opened_file.readline.return_value = ha_version
        hass.config.path = mock.Mock()
        config_util.process_ha_config_upgrade(hass)
        hass_path = hass.config.path.return_value

        assert mock_os.path.isdir.call_count == 1
        assert mock_os.path.isdir.call_args == mock.call(hass_path)
        assert mock_shutil.rmtree.call_count == 1
        assert mock_shutil.rmtree.call_args == mock.call(hass_path)


@patch("homeassistant.config.shutil")
@patch("homeassistant.config.os")
@patch("homeassistant.config.is_docker_env", return_value=True)
def test_remove_lib_on_upgrade_94(
    mock_docker, mock_os, mock_shutil, hass: HomeAssistant
) -> None:
    """Test removal of library on upgrade from before 0.94 and in Docker."""
    ha_version = "0.93.0.dev0"
    mock_os.path.isdir = mock.Mock(return_value=True)
    mock_open = mock.mock_open()
    with patch("homeassistant.config.open", mock_open, create=True):
        opened_file = mock_open.return_value
        opened_file.readline.return_value = ha_version
        hass.config.path = mock.Mock()
        config_util.process_ha_config_upgrade(hass)
        hass_path = hass.config.path.return_value

        assert mock_os.path.isdir.call_count == 1
        assert mock_os.path.isdir.call_args == mock.call(hass_path)
        assert mock_shutil.rmtree.call_count == 1
        assert mock_shutil.rmtree.call_args == mock.call(hass_path)


def test_process_config_upgrade(hass: HomeAssistant) -> None:
    """Test update of version on upgrade."""
    ha_version = "0.92.0"

    mock_open = mock.mock_open()
    with (
        patch("homeassistant.config.open", mock_open, create=True),
        patch.object(config_util, "__version__", "0.91.0"),
    ):
        opened_file = mock_open.return_value
        opened_file.readline.return_value = ha_version

        config_util.process_ha_config_upgrade(hass)

        assert opened_file.write.call_count == 1
        assert opened_file.write.call_args == mock.call("0.91.0")


def test_config_upgrade_same_version(hass: HomeAssistant) -> None:
    """Test no update of version on no upgrade."""
    ha_version = __version__

    mock_open = mock.mock_open()
    with patch("homeassistant.config.open", mock_open, create=True):
        opened_file = mock_open.return_value
        opened_file.readline.return_value = ha_version

        config_util.process_ha_config_upgrade(hass)

        assert opened_file.write.call_count == 0


def test_config_upgrade_no_file(hass: HomeAssistant) -> None:
    """Test update of version on upgrade, with no version file."""
    mock_open = mock.mock_open()
    mock_open.side_effect = [FileNotFoundError(), mock.DEFAULT, mock.DEFAULT]
    with patch("homeassistant.config.open", mock_open, create=True):
        opened_file = mock_open.return_value
        config_util.process_ha_config_upgrade(hass)
        assert opened_file.write.call_count == 1
        assert opened_file.write.call_args == mock.call(__version__)


async def test_loading_configuration_from_storage(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test loading core config onto hass object."""
    hass_storage["core.config"] = {
        "data": {
            "elevation": 10,
            "latitude": 55,
            "location_name": "Home",
            "longitude": 13,
            "time_zone": "Europe/Copenhagen",
            "unit_system": "metric",
            "external_url": "https://www.example.com",
            "internal_url": "http://example.local",
            "currency": "EUR",
            "country": "SE",
            "language": "sv",
        },
        "key": "core.config",
        "version": 1,
        "minor_version": 3,
    }
    await config_util.async_process_ha_core_config(
        hass, {"allowlist_external_dirs": "/etc"}
    )

    assert hass.config.latitude == 55
    assert hass.config.longitude == 13
    assert hass.config.elevation == 10
    assert hass.config.location_name == "Home"
    assert hass.config.units is METRIC_SYSTEM
    assert hass.config.time_zone == "Europe/Copenhagen"
    assert hass.config.external_url == "https://www.example.com"
    assert hass.config.internal_url == "http://example.local"
    assert hass.config.currency == "EUR"
    assert hass.config.country == "SE"
    assert hass.config.language == "sv"
    assert len(hass.config.allowlist_external_dirs) == 3
    assert "/etc" in hass.config.allowlist_external_dirs
    assert hass.config.config_source is ConfigSource.STORAGE


async def test_loading_configuration_from_storage_with_yaml_only(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test loading core and YAML config onto hass object."""
    hass_storage["core.config"] = {
        "data": {
            "elevation": 10,
            "latitude": 55,
            "location_name": "Home",
            "longitude": 13,
            "time_zone": "Europe/Copenhagen",
            "unit_system": "metric",
        },
        "key": "core.config",
        "version": 1,
    }
    await config_util.async_process_ha_core_config(
        hass, {"media_dirs": {"mymedia": "/usr"}, "allowlist_external_dirs": "/etc"}
    )

    assert hass.config.latitude == 55
    assert hass.config.longitude == 13
    assert hass.config.elevation == 10
    assert hass.config.location_name == "Home"
    assert hass.config.units is METRIC_SYSTEM
    assert hass.config.time_zone == "Europe/Copenhagen"
    assert len(hass.config.allowlist_external_dirs) == 3
    assert "/etc" in hass.config.allowlist_external_dirs
    assert hass.config.media_dirs == {"mymedia": "/usr"}
    assert hass.config.config_source is ConfigSource.STORAGE


async def test_migration_and_updating_configuration(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test updating configuration stores the new configuration."""
    core_data = {
        "data": {
            "elevation": 10,
            "latitude": 55,
            "location_name": "Home",
            "longitude": 13,
            "time_zone": "Europe/Copenhagen",
            "unit_system": "imperial",
            "external_url": "https://www.example.com",
            "internal_url": "http://example.local",
            "currency": "BTC",
        },
        "key": "core.config",
        "version": 1,
        "minor_version": 1,
    }
    hass_storage["core.config"] = dict(core_data)
    await config_util.async_process_ha_core_config(
        hass, {"allowlist_external_dirs": "/etc"}
    )
    await hass.config.async_update(latitude=50, currency="USD")

    expected_new_core_data = copy.deepcopy(core_data)
    # From async_update above
    expected_new_core_data["data"]["latitude"] = 50
    expected_new_core_data["data"]["currency"] = "USD"
    # 1.1 -> 1.2 store migration with migrated unit system
    expected_new_core_data["data"]["unit_system_v2"] = "us_customary"
    expected_new_core_data["minor_version"] = 3
    # defaults for country and language
    expected_new_core_data["data"]["country"] = None
    expected_new_core_data["data"]["language"] = "en"
    assert hass_storage["core.config"] == expected_new_core_data
    assert hass.config.latitude == 50
    assert hass.config.currency == "USD"
    assert hass.config.country is None
    assert hass.config.language == "en"


async def test_override_stored_configuration(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test loading core and YAML config onto hass object."""
    hass_storage["core.config"] = {
        "data": {
            "elevation": 10,
            "latitude": 55,
            "location_name": "Home",
            "longitude": 13,
            "time_zone": "Europe/Copenhagen",
            "unit_system": "metric",
        },
        "key": "core.config",
        "version": 1,
    }
    await config_util.async_process_ha_core_config(
        hass, {"latitude": 60, "allowlist_external_dirs": "/etc"}
    )

    assert hass.config.latitude == 60
    assert hass.config.longitude == 13
    assert hass.config.elevation == 10
    assert hass.config.location_name == "Home"
    assert hass.config.units is METRIC_SYSTEM
    assert hass.config.time_zone == "Europe/Copenhagen"
    assert len(hass.config.allowlist_external_dirs) == 3
    assert "/etc" in hass.config.allowlist_external_dirs
    assert hass.config.config_source is ConfigSource.YAML


async def test_loading_configuration(hass: HomeAssistant) -> None:
    """Test loading core config onto hass object."""
    await config_util.async_process_ha_core_config(
        hass,
        {
            "latitude": 60,
            "longitude": 50,
            "elevation": 25,
            "name": "Huis",
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
            "time_zone": "America/New_York",
            "allowlist_external_dirs": "/etc",
            "external_url": "https://www.example.com",
            "internal_url": "http://example.local",
            "media_dirs": {"mymedia": "/usr"},
            "legacy_templates": True,
            "debug": True,
            "currency": "EUR",
            "country": "SE",
            "language": "sv",
        },
    )

    assert hass.config.latitude == 60
    assert hass.config.longitude == 50
    assert hass.config.elevation == 25
    assert hass.config.location_name == "Huis"
    assert hass.config.units is US_CUSTOMARY_SYSTEM
    assert hass.config.time_zone == "America/New_York"
    assert hass.config.external_url == "https://www.example.com"
    assert hass.config.internal_url == "http://example.local"
    assert len(hass.config.allowlist_external_dirs) == 3
    assert "/etc" in hass.config.allowlist_external_dirs
    assert "/usr" in hass.config.allowlist_external_dirs
    assert hass.config.media_dirs == {"mymedia": "/usr"}
    assert hass.config.config_source is ConfigSource.YAML
    assert hass.config.legacy_templates is True
    assert hass.config.debug is True
    assert hass.config.currency == "EUR"
    assert hass.config.country == "SE"
    assert hass.config.language == "sv"


@pytest.mark.parametrize(
    ("minor_version", "users", "user_data", "default_language"),
    [
        (2, (), {}, "en"),
        (2, ({"is_owner": True},), {}, "en"),
        (
            2,
            ({"id": "user1", "is_owner": True},),
            {"user1": {"language": {"language": "sv"}}},
            "sv",
        ),
        (
            2,
            ({"id": "user1", "is_owner": False},),
            {"user1": {"language": {"language": "sv"}}},
            "en",
        ),
        (3, (), {}, "en"),
        (3, ({"is_owner": True},), {}, "en"),
        (
            3,
            ({"id": "user1", "is_owner": True},),
            {"user1": {"language": {"language": "sv"}}},
            "en",
        ),
        (
            3,
            ({"id": "user1", "is_owner": False},),
            {"user1": {"language": {"language": "sv"}}},
            "en",
        ),
    ],
)
async def test_language_default(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    minor_version,
    users,
    user_data,
    default_language,
) -> None:
    """Test language config default to owner user's language during migration.

    This should only happen if the core store version < 1.3
    """
    core_data = {
        "data": {},
        "key": "core.config",
        "version": 1,
        "minor_version": minor_version,
    }
    hass_storage["core.config"] = dict(core_data)

    for user_config in users:
        user = MockUser(**user_config).add_to_hass(hass)
        if user.id not in user_data:
            continue
        storage_key = f"frontend.user_data_{user.id}"
        hass_storage[storage_key] = {
            "key": storage_key,
            "version": 1,
            "data": user_data[user.id],
        }

    await config_util.async_process_ha_core_config(
        hass,
        {},
    )
    assert hass.config.language == default_language


async def test_loading_configuration_default_media_dirs_docker(
    hass: HomeAssistant,
) -> None:
    """Test loading core config onto hass object."""
    with patch("homeassistant.config.is_docker_env", return_value=True):
        await config_util.async_process_ha_core_config(
            hass,
            {
                "name": "Huis",
            },
        )

    assert hass.config.location_name == "Huis"
    assert len(hass.config.allowlist_external_dirs) == 2
    assert "/media" in hass.config.allowlist_external_dirs
    assert hass.config.media_dirs == {"local": "/media"}


async def test_loading_configuration_from_packages(hass: HomeAssistant) -> None:
    """Test loading packages config onto hass object config."""
    await config_util.async_process_ha_core_config(
        hass,
        {
            "latitude": 39,
            "longitude": -1,
            "elevation": 500,
            "name": "Huis",
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
            "time_zone": "Europe/Madrid",
            "external_url": "https://www.example.com",
            "internal_url": "http://example.local",
            "packages": {
                "package_1": {"wake_on_lan": None},
                "package_2": {
                    "light": {"platform": "hue"},
                    "media_extractor": None,
                    "sun": None,
                },
            },
        },
    )

    # Empty packages not allowed
    with pytest.raises(MultipleInvalid):
        await config_util.async_process_ha_core_config(
            hass,
            {
                "latitude": 39,
                "longitude": -1,
                "elevation": 500,
                "name": "Huis",
                CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
                "time_zone": "Europe/Madrid",
                "packages": {"empty_package": None},
            },
        )


@pytest.mark.parametrize(
    ("unit_system_name", "expected_unit_system"),
    [
        (CONF_UNIT_SYSTEM_METRIC, METRIC_SYSTEM),
        (CONF_UNIT_SYSTEM_IMPERIAL, US_CUSTOMARY_SYSTEM),
        (_CONF_UNIT_SYSTEM_US_CUSTOMARY, US_CUSTOMARY_SYSTEM),
    ],
)
async def test_loading_configuration_unit_system(
    hass: HomeAssistant, unit_system_name: str, expected_unit_system: UnitSystem
) -> None:
    """Test backward compatibility when loading core config."""
    await config_util.async_process_ha_core_config(
        hass,
        {
            "latitude": 60,
            "longitude": 50,
            "elevation": 25,
            "name": "Huis",
            "unit_system": unit_system_name,
            "time_zone": "America/New_York",
            "external_url": "https://www.example.com",
            "internal_url": "http://example.local",
        },
    )

    assert hass.config.units is expected_unit_system


@patch("homeassistant.helpers.check_config.async_check_ha_config_file")
async def test_check_ha_config_file_correct(mock_check, hass: HomeAssistant) -> None:
    """Check that restart propagates to stop."""
    mock_check.return_value = check_config.HomeAssistantConfig()
    assert await config_util.async_check_ha_config_file(hass) is None


@patch("homeassistant.helpers.check_config.async_check_ha_config_file")
async def test_check_ha_config_file_wrong(mock_check, hass: HomeAssistant) -> None:
    """Check that restart with a bad config doesn't propagate to stop."""
    mock_check.return_value = check_config.HomeAssistantConfig()
    mock_check.return_value.add_error("bad")

    assert await config_util.async_check_ha_config_file(hass) == "bad"


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            HA_DOMAIN: {
                config_util.CONF_PACKAGES: {
                    "pack_dict": {"input_boolean": {"ib1": None}}
                }
            },
            "input_boolean": {"ib2": None},
            "light": {"platform": "test"},
        }
    ],
)
async def test_async_hass_config_yaml_merge(
    merge_log_err, hass: HomeAssistant, mock_hass_config: None
) -> None:
    """Test merge during async config reload."""
    conf = await config_util.async_hass_config_yaml(hass)

    assert merge_log_err.call_count == 0
    assert conf[HA_DOMAIN].get(config_util.CONF_PACKAGES) is not None
    assert len(conf) == 3
    assert len(conf["input_boolean"]) == 2
    assert len(conf["light"]) == 1


@pytest.fixture
def merge_log_err(hass):
    """Patch _merge_log_error from packages."""
    with patch("homeassistant.config._LOGGER.error") as logerr:
        yield logerr


async def test_merge(merge_log_err, hass: HomeAssistant) -> None:
    """Test if we can merge packages."""
    packages = {
        "pack_dict": {"input_boolean": {"ib1": None}},
        "pack_11": {"input_select": {"is1": None}},
        "pack_list": {"light": {"platform": "test"}},
        "pack_list2": {"light": [{"platform": "test"}]},
        "pack_none": {"wake_on_lan": None},
        "pack_special": {
            "automation": [{"some": "yay"}],
            "script": {"a_script": "yay"},
            "template": [{"some": "yay"}],
        },
    }
    config = {
        HA_DOMAIN: {config_util.CONF_PACKAGES: packages},
        "input_boolean": {"ib2": None},
        "light": {"platform": "test"},
        "automation": [],
        "script": {},
        "template": [],
    }
    await config_util.merge_packages_config(hass, config, packages)

    assert merge_log_err.call_count == 0
    assert len(config) == 8
    assert len(config["input_boolean"]) == 2
    assert len(config["input_select"]) == 1
    assert len(config["light"]) == 3
    assert len(config["automation"]) == 1
    assert len(config["script"]) == 1
    assert len(config["template"]) == 1
    assert isinstance(config["wake_on_lan"], OrderedDict)


async def test_merge_try_falsy(merge_log_err, hass: HomeAssistant) -> None:
    """Ensure we don't add falsy items like empty OrderedDict() to list."""
    packages = {
        "pack_falsy_to_lst": {"automation": OrderedDict()},
        "pack_list2": {"light": OrderedDict()},
    }
    config = {
        HA_DOMAIN: {config_util.CONF_PACKAGES: packages},
        "automation": {"do": "something"},
        "light": {"some": "light"},
    }
    await config_util.merge_packages_config(hass, config, packages)

    assert merge_log_err.call_count == 0
    assert len(config) == 3
    assert len(config["automation"]) == 1
    assert len(config["light"]) == 1


async def test_merge_new(merge_log_err, hass: HomeAssistant) -> None:
    """Test adding new components to outer scope."""
    packages = {
        "pack_1": {"light": [{"platform": "one"}]},
        "pack_11": {"input_select": {"ib1": None}},
        "pack_2": {
            "light": {"platform": "one"},
            "panel_custom": {"pan1": None},
            "api": {},
        },
    }
    config = {HA_DOMAIN: {config_util.CONF_PACKAGES: packages}}
    await config_util.merge_packages_config(hass, config, packages)

    assert merge_log_err.call_count == 0
    assert "api" in config
    assert len(config) == 5
    assert len(config["light"]) == 2
    assert len(config["panel_custom"]) == 1


async def test_merge_type_mismatch(merge_log_err, hass: HomeAssistant) -> None:
    """Test if we have a type mismatch for packages."""
    packages = {
        "pack_1": {"input_boolean": [{"ib1": None}]},
        "pack_11": {"input_select": {"ib1": None}},
        "pack_2": {"light": {"ib1": None}},  # light gets merged - ensure_list
    }
    config = {
        HA_DOMAIN: {config_util.CONF_PACKAGES: packages},
        "input_boolean": {"ib2": None},
        "input_select": [{"ib2": None}],
        "light": [{"platform": "two"}],
    }
    await config_util.merge_packages_config(hass, config, packages)

    assert merge_log_err.call_count == 2
    assert len(config) == 4
    assert len(config["input_boolean"]) == 1
    assert len(config["light"]) == 2


async def test_merge_once_only_keys(merge_log_err, hass: HomeAssistant) -> None:
    """Test if we have a merge for a comp that may occur only once. Keys."""
    packages = {"pack_2": {"api": None}}
    config = {HA_DOMAIN: {config_util.CONF_PACKAGES: packages}, "api": None}
    await config_util.merge_packages_config(hass, config, packages)
    assert config["api"] == OrderedDict()

    packages = {"pack_2": {"api": {"key_3": 3}}}
    config = {
        HA_DOMAIN: {config_util.CONF_PACKAGES: packages},
        "api": {"key_1": 1, "key_2": 2},
    }
    await config_util.merge_packages_config(hass, config, packages)
    assert config["api"] == {"key_1": 1, "key_2": 2, "key_3": 3}

    # Duplicate keys error
    packages = {"pack_2": {"api": {"key": 2}}}
    config = {
        HA_DOMAIN: {config_util.CONF_PACKAGES: packages},
        "api": {"key": 1},
    }
    await config_util.merge_packages_config(hass, config, packages)
    assert merge_log_err.call_count == 1


async def test_merge_once_only_lists(hass: HomeAssistant) -> None:
    """Test if we have a merge for a comp that may occur only once. Lists."""
    packages = {
        "pack_2": {
            "api": {"list_1": ["item_2", "item_3"], "list_2": ["item_4"], "list_3": []}
        }
    }
    config = {
        HA_DOMAIN: {config_util.CONF_PACKAGES: packages},
        "api": {"list_1": ["item_1"]},
    }
    await config_util.merge_packages_config(hass, config, packages)
    assert config["api"] == {
        "list_1": ["item_1", "item_2", "item_3"],
        "list_2": ["item_4"],
        "list_3": [],
    }


async def test_merge_once_only_dictionaries(hass: HomeAssistant) -> None:
    """Test if we have a merge for a comp that may occur only once. Dicts."""
    packages = {
        "pack_2": {
            "api": {
                "dict_1": {"key_2": 2, "dict_1.1": {"key_1.2": 1.2}},
                "dict_2": {"key_1": 1},
                "dict_3": {},
            }
        }
    }
    config = {
        HA_DOMAIN: {config_util.CONF_PACKAGES: packages},
        "api": {"dict_1": {"key_1": 1, "dict_1.1": {"key_1.1": 1.1}}},
    }
    await config_util.merge_packages_config(hass, config, packages)
    assert config["api"] == {
        "dict_1": {
            "key_1": 1,
            "key_2": 2,
            "dict_1.1": {"key_1.1": 1.1, "key_1.2": 1.2},
        },
        "dict_2": {"key_1": 1},
    }


async def test_merge_id_schema(hass: HomeAssistant) -> None:
    """Test if we identify the config schemas correctly."""
    types = {
        "panel_custom": "list",
        "group": "dict",
        "input_boolean": "dict",
        "shell_command": "dict",
        "qwikswitch": "dict",
    }
    for domain, expected_type in types.items():
        integration = await async_get_integration(hass, domain)
        module = integration.get_component()
        typ = config_util._identify_config_schema(module)
        assert typ == expected_type, f"{domain} expected {expected_type}, got {typ}"


async def test_merge_duplicate_keys(merge_log_err, hass: HomeAssistant) -> None:
    """Test if keys in dicts are duplicates."""
    packages = {"pack_1": {"input_select": {"ib1": None}}}
    config = {
        HA_DOMAIN: {config_util.CONF_PACKAGES: packages},
        "input_select": {"ib1": 1},
    }
    await config_util.merge_packages_config(hass, config, packages)

    assert merge_log_err.call_count == 1
    assert len(config) == 2
    assert len(config["input_select"]) == 1


async def test_merge_customize(hass: HomeAssistant) -> None:
    """Test loading core config onto hass object."""
    core_config = {
        "latitude": 60,
        "longitude": 50,
        "elevation": 25,
        "name": "Huis",
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
        "time_zone": "GMT",
        "customize": {"a.a": {"friendly_name": "A"}},
        "packages": {
            "pkg1": {"homeassistant": {"customize": {"b.b": {"friendly_name": "BB"}}}}
        },
    }
    await config_util.async_process_ha_core_config(hass, core_config)

    assert hass.data[config_util.DATA_CUSTOMIZE].get("b.b") == {"friendly_name": "BB"}


async def test_auth_provider_config(hass: HomeAssistant) -> None:
    """Test loading auth provider config onto hass object."""
    core_config = {
        "latitude": 60,
        "longitude": 50,
        "elevation": 25,
        "name": "Huis",
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
        "time_zone": "GMT",
        CONF_AUTH_PROVIDERS: [
            {"type": "homeassistant"},
            {"type": "legacy_api_password", "api_password": "some-pass"},
        ],
        CONF_AUTH_MFA_MODULES: [{"type": "totp"}, {"type": "totp", "id": "second"}],
    }
    if hasattr(hass, "auth"):
        del hass.auth
    await config_util.async_process_ha_core_config(hass, core_config)

    assert len(hass.auth.auth_providers) == 2
    assert hass.auth.auth_providers[0].type == "homeassistant"
    assert hass.auth.auth_providers[1].type == "legacy_api_password"
    assert len(hass.auth.auth_mfa_modules) == 2
    assert hass.auth.auth_mfa_modules[0].id == "totp"
    assert hass.auth.auth_mfa_modules[1].id == "second"


async def test_auth_provider_config_default(hass: HomeAssistant) -> None:
    """Test loading default auth provider config."""
    core_config = {
        "latitude": 60,
        "longitude": 50,
        "elevation": 25,
        "name": "Huis",
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
        "time_zone": "GMT",
    }
    if hasattr(hass, "auth"):
        del hass.auth
    await config_util.async_process_ha_core_config(hass, core_config)

    assert len(hass.auth.auth_providers) == 1
    assert hass.auth.auth_providers[0].type == "homeassistant"
    assert len(hass.auth.auth_mfa_modules) == 1
    assert hass.auth.auth_mfa_modules[0].id == "totp"


async def test_disallowed_auth_provider_config(hass: HomeAssistant) -> None:
    """Test loading insecure example auth provider is disallowed."""
    core_config = {
        "latitude": 60,
        "longitude": 50,
        "elevation": 25,
        "name": "Huis",
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
        "time_zone": "GMT",
        CONF_AUTH_PROVIDERS: [
            {
                "type": "insecure_example",
                "users": [
                    {
                        "username": "test-user",
                        "password": "test-pass",
                        "name": "Test Name",
                    }
                ],
            }
        ],
    }
    with pytest.raises(Invalid):
        await config_util.async_process_ha_core_config(hass, core_config)


async def test_disallowed_duplicated_auth_provider_config(hass: HomeAssistant) -> None:
    """Test loading insecure example auth provider is disallowed."""
    core_config = {
        "latitude": 60,
        "longitude": 50,
        "elevation": 25,
        "name": "Huis",
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
        "time_zone": "GMT",
        CONF_AUTH_PROVIDERS: [{"type": "homeassistant"}, {"type": "homeassistant"}],
    }
    with pytest.raises(Invalid):
        await config_util.async_process_ha_core_config(hass, core_config)


async def test_disallowed_auth_mfa_module_config(hass: HomeAssistant) -> None:
    """Test loading insecure example auth mfa module is disallowed."""
    core_config = {
        "latitude": 60,
        "longitude": 50,
        "elevation": 25,
        "name": "Huis",
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
        "time_zone": "GMT",
        CONF_AUTH_MFA_MODULES: [
            {
                "type": "insecure_example",
                "data": [{"user_id": "mock-user", "pin": "test-pin"}],
            }
        ],
    }
    with pytest.raises(Invalid):
        await config_util.async_process_ha_core_config(hass, core_config)


async def test_disallowed_duplicated_auth_mfa_module_config(
    hass: HomeAssistant,
) -> None:
    """Test loading insecure example auth mfa module is disallowed."""
    core_config = {
        "latitude": 60,
        "longitude": 50,
        "elevation": 25,
        "name": "Huis",
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
        "time_zone": "GMT",
        CONF_AUTH_MFA_MODULES: [{"type": "totp"}, {"type": "totp"}],
    }
    with pytest.raises(Invalid):
        await config_util.async_process_ha_core_config(hass, core_config)


async def test_merge_split_component_definition(hass: HomeAssistant) -> None:
    """Test components with trailing description in packages are merged."""
    packages = {
        "pack_1": {"light one": {"l1": None}},
        "pack_2": {"light two": {"l2": None}, "light three": {"l3": None}},
    }
    config = {HA_DOMAIN: {config_util.CONF_PACKAGES: packages}}
    await config_util.merge_packages_config(hass, config, packages)

    assert len(config) == 4
    assert len(config["light one"]) == 1
    assert len(config["light two"]) == 1
    assert len(config["light three"]) == 1


async def test_component_config_exceptions(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test unexpected exceptions validating component config."""

    # Create test config with embedded info
    test_config = ConfigTestClass({"test_domain": {}})
    test_platform_config = ConfigTestClass(
        {"test_domain": {"platform": "test_platform"}}
    )
    test_multi_platform_config = ConfigTestClass(
        {
            "test_domain": [
                {"platform": "test_platform1"},
                {"platform": "test_platform2"},
            ]
        },
    )

    # Make sure the exception translation cache is loaded
    await async_setup_component(hass, "homeassistant", {})

    test_integration = Mock(
        domain="test_domain",
        async_get_component=AsyncMock(),
        async_get_platform=AsyncMock(
            return_value=Mock(
                async_validate_config=AsyncMock(side_effect=ValueError("broken"))
            )
        ),
    )
    assert (
        await config_util.async_process_component_and_handle_errors(
            hass, test_config, integration=test_integration
        )
        is None
    )
    assert "ValueError: broken" in caplog.text
    assert "Unknown error calling test_domain config validator" in caplog.text
    caplog.clear()
    with pytest.raises(HomeAssistantError) as ex:
        await config_util.async_process_component_and_handle_errors(
            hass, test_config, integration=test_integration, raise_on_failure=True
        )
    assert "ValueError: broken" in caplog.text
    assert "Unknown error calling test_domain config validator" in caplog.text
    assert (
        str(ex.value) == "Unknown error calling test_domain config validator - broken"
    )
    test_integration = Mock(
        domain="test_domain",
        async_get_platform=AsyncMock(
            return_value=Mock(
                async_validate_config=AsyncMock(
                    side_effect=HomeAssistantError("broken")
                )
            )
        ),
        async_get_component=AsyncMock(return_value=Mock(spec=["PLATFORM_SCHEMA_BASE"])),
    )
    caplog.clear()
    assert (
        await config_util.async_process_component_and_handle_errors(
            hass, test_config, integration=test_integration, raise_on_failure=False
        )
        is None
    )
    assert (
        "Invalid config for 'test_domain' at ../../configuration.yaml, "
        "line 140: broken, please check the docs at" in caplog.text
    )
    with pytest.raises(HomeAssistantError) as ex:
        await config_util.async_process_component_and_handle_errors(
            hass, test_config, integration=test_integration, raise_on_failure=True
        )
    assert (
        str(ex.value)
        == "Invalid config for integration test_domain at configuration.yaml, "
        "line 140: broken"
    )
    # component.CONFIG_SCHEMA
    caplog.clear()
    test_integration = Mock(
        domain="test_domain",
        async_get_platform=AsyncMock(return_value=None),
        async_get_component=AsyncMock(
            return_value=Mock(CONFIG_SCHEMA=Mock(side_effect=ValueError("broken")))
        ),
    )
    assert (
        await config_util.async_process_component_and_handle_errors(
            hass,
            test_config,
            integration=test_integration,
            raise_on_failure=False,
        )
        is None
    )
    assert "Unknown error calling test_domain CONFIG_SCHEMA" in caplog.text
    caplog.clear()
    with pytest.raises(HomeAssistantError) as ex:
        await config_util.async_process_component_and_handle_errors(
            hass,
            test_config,
            integration=test_integration,
            raise_on_failure=True,
        )
    assert "Unknown error calling test_domain CONFIG_SCHEMA" in caplog.text
    assert str(ex.value) == "Unknown error calling test_domain CONFIG_SCHEMA - broken"
    # component.PLATFORM_SCHEMA
    caplog.clear()
    test_integration = Mock(
        domain="test_domain",
        async_get_platform=AsyncMock(return_value=None),
        async_get_component=AsyncMock(
            return_value=Mock(
                spec=["PLATFORM_SCHEMA_BASE"],
                PLATFORM_SCHEMA_BASE=Mock(side_effect=ValueError("broken")),
            )
        ),
    )
    assert await config_util.async_process_component_and_handle_errors(
        hass,
        test_platform_config,
        integration=test_integration,
        raise_on_failure=False,
    ) == {"test_domain": []}
    assert "ValueError: broken" in caplog.text
    assert (
        "Unknown error when validating config for test_domain "
        "from integration test_platform - broken"
    ) in caplog.text
    caplog.clear()
    with pytest.raises(HomeAssistantError) as ex:
        await config_util.async_process_component_and_handle_errors(
            hass,
            test_platform_config,
            integration=test_integration,
            raise_on_failure=True,
        )
    assert (
        "Unknown error when validating config for test_domain "
        "from integration test_platform - broken"
    ) in caplog.text
    assert str(ex.value) == (
        "Unknown error when validating config for test_domain "
        "from integration test_platform - broken"
    )

    # platform.PLATFORM_SCHEMA
    caplog.clear()
    test_integration = Mock(
        domain="test_domain",
        async_get_platform=AsyncMock(return_value=None),
        async_get_component=AsyncMock(return_value=Mock(spec=["PLATFORM_SCHEMA_BASE"])),
    )
    with patch(
        "homeassistant.config.async_get_integration_with_requirements",
        return_value=Mock(  # integration that owns platform
            async_get_platform=AsyncMock(
                return_value=Mock(  # platform
                    PLATFORM_SCHEMA=Mock(side_effect=ValueError("broken"))
                )
            )
        ),
    ):
        assert await config_util.async_process_component_and_handle_errors(
            hass,
            test_platform_config,
            integration=test_integration,
            raise_on_failure=False,
        ) == {"test_domain": []}
        assert "ValueError: broken" in caplog.text
        assert (
            "Unknown error when validating config for test_domain "
            "from integration test_platform - broken"
        ) in caplog.text
        caplog.clear()
        with pytest.raises(HomeAssistantError) as ex:
            assert await config_util.async_process_component_and_handle_errors(
                hass,
                test_platform_config,
                integration=test_integration,
                raise_on_failure=True,
            )
        assert (
            "Unknown error when validating config for test_domain "
            "from integration test_platform - broken" in str(ex.value)
        )
        assert "ValueError: broken" in caplog.text
        assert (
            "Unknown error when validating config for test_domain "
            "from integration test_platform - broken" in caplog.text
        )
        # Test multiple platform failures
        assert await config_util.async_process_component_and_handle_errors(
            hass,
            test_multi_platform_config,
            integration=test_integration,
            raise_on_failure=False,
        ) == {"test_domain": []}
        assert "ValueError: broken" in caplog.text
        assert (
            "Unknown error when validating config for test_domain "
            "from integration test_platform - broken"
        ) in caplog.text
        caplog.clear()
        with pytest.raises(HomeAssistantError) as ex:
            assert await config_util.async_process_component_and_handle_errors(
                hass,
                test_multi_platform_config,
                integration=test_integration,
                raise_on_failure=True,
            )
        assert (
            "Failed to process config for integration test_domain "
            "due to multiple (2) errors. Check the logs for more information"
            in str(ex.value)
        )
        assert "ValueError: broken" in caplog.text
        assert (
            "Unknown error when validating config for test_domain "
            "from integration test_platform1 - broken"
        ) in caplog.text
        assert (
            "Unknown error when validating config for test_domain "
            "from integration test_platform2 - broken"
        ) in caplog.text

    # async_get_platform("domain") raising on ImportError
    caplog.clear()
    test_integration = Mock(
        domain="test_domain",
        async_get_platform=AsyncMock(return_value=None),
        async_get_component=AsyncMock(return_value=Mock(spec=["PLATFORM_SCHEMA_BASE"])),
    )
    import_error = ImportError(
        ("ModuleNotFoundError: No module named 'not_installed_something'"),
        name="not_installed_something",
    )
    with patch(
        "homeassistant.config.async_get_integration_with_requirements",
        return_value=Mock(  # integration that owns platform
            async_get_platform=AsyncMock(side_effect=import_error)
        ),
    ):
        assert await config_util.async_process_component_and_handle_errors(
            hass,
            test_platform_config,
            integration=test_integration,
            raise_on_failure=False,
        ) == {"test_domain": []}
        assert (
            "ImportError: ModuleNotFoundError: No module named "
            "'not_installed_something'" in caplog.text
        )
        caplog.clear()
        with pytest.raises(HomeAssistantError) as ex:
            assert await config_util.async_process_component_and_handle_errors(
                hass,
                test_platform_config,
                integration=test_integration,
                raise_on_failure=True,
            )
        assert (
            "ImportError: ModuleNotFoundError: No module named "
            "'not_installed_something'" in caplog.text
        )
        assert (
            "Platform error: test_domain - ModuleNotFoundError: "
            "No module named 'not_installed_something'"
        ) in caplog.text
        assert (
            "Platform error: test_domain - ModuleNotFoundError: "
            "No module named 'not_installed_something'"
        ) in str(ex.value)

    # async_get_platform("config") raising
    caplog.clear()
    test_integration = Mock(
        pkg_path="homeassistant.components.test_domain",
        domain="test_domain",
        async_get_component=AsyncMock(),
        async_get_platform=AsyncMock(
            side_effect=ImportError(
                ("ModuleNotFoundError: No module named 'not_installed_something'"),
                name="not_installed_something",
            )
        ),
    )
    assert (
        await config_util.async_process_component_and_handle_errors(
            hass,
            test_config,
            integration=test_integration,
            raise_on_failure=False,
        )
        is None
    )
    assert (
        "Error importing config platform test_domain: ModuleNotFoundError: "
        "No module named 'not_installed_something'" in caplog.text
    )
    with pytest.raises(HomeAssistantError) as ex:
        await config_util.async_process_component_and_handle_errors(
            hass,
            test_config,
            integration=test_integration,
            raise_on_failure=True,
        )
    assert (
        "Error importing config platform test_domain: ModuleNotFoundError: "
        "No module named 'not_installed_something'" in caplog.text
    )
    assert (
        "Error importing config platform test_domain: ModuleNotFoundError: "
        "No module named 'not_installed_something'" in str(ex.value)
    )

    # async_get_component raising
    caplog.clear()
    test_integration = Mock(
        pkg_path="homeassistant.components.test_domain",
        domain="test_domain",
        async_get_component=AsyncMock(
            side_effect=FileNotFoundError("No such file or directory: b'liblibc.a'")
        ),
    )
    assert (
        await config_util.async_process_component_and_handle_errors(
            hass,
            test_config,
            integration=test_integration,
            raise_on_failure=False,
        )
        is None
    )
    assert "Unable to import test_domain: No such file or directory" in caplog.text
    with pytest.raises(HomeAssistantError) as ex:
        await config_util.async_process_component_and_handle_errors(
            hass,
            test_config,
            integration=test_integration,
            raise_on_failure=True,
        )
    assert "Unable to import test_domain: No such file or directory" in caplog.text
    assert "Unable to import test_domain: No such file or directory" in str(ex.value)


@pytest.mark.parametrize(
    ("exception_info_list", "error", "messages", "show_stack_trace", "translation_key"),
    [
        (
            [
                config_util.ConfigExceptionInfo(
                    ImportError("bla"),
                    "component_import_err",
                    "test_domain",
                    ConfigTestClass({"test_domain": []}),
                    "https://example.com",
                )
            ],
            "bla",
            ["Unable to import test_domain: bla", "bla"],
            False,
            "component_import_err",
        ),
        (
            [
                config_util.ConfigExceptionInfo(
                    HomeAssistantError("bla"),
                    "config_validation_err",
                    "test_domain",
                    ConfigTestClass({"test_domain": []}),
                    "https://example.com",
                )
            ],
            "bla",
            [
                "Invalid config for 'test_domain' at "
                "../../configuration.yaml, line 140: bla, "
                "please check the docs at https://example.com",
                "bla",
            ],
            True,
            "config_validation_err",
        ),
        (
            [
                config_util.ConfigExceptionInfo(
                    vol.Invalid("bla", ["path"]),
                    "config_validation_err",
                    "test_domain",
                    ConfigTestClass({"test_domain": []}),
                    "https://example.com",
                )
            ],
            "bla @ data['path']",
            [
                "Invalid config for 'test_domain' at "
                "../../configuration.yaml, line 140: bla 'path', "
                "got None, please check the docs at https://example.com",
                "bla",
            ],
            False,
            "config_validation_err",
        ),
        (
            [
                config_util.ConfigExceptionInfo(
                    vol.Invalid("bla", ["path"]),
                    "platform_config_validation_err",
                    "test_domain",
                    ConfigTestClass({"test_domain": []}),
                    "https://alt.example.com",
                )
            ],
            "bla @ data['path']",
            [
                "Invalid config for 'test_domain' at "
                "../../configuration.yaml, line 140: bla 'path', "
                "got None, please check the docs at https://alt.example.com",
                "bla",
            ],
            False,
            "platform_config_validation_err",
        ),
        (
            [
                config_util.ConfigExceptionInfo(
                    ImportError("bla"),
                    "platform_component_load_err",
                    "test_domain",
                    ConfigTestClass({"test_domain": []}),
                    "https://example.com",
                )
            ],
            "bla",
            ["Platform error: test_domain - bla", "bla"],
            False,
            "platform_component_load_err",
        ),
    ],
)
async def test_component_config_error_processing(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    exception_info_list: list[config_util.ConfigExceptionInfo],
    snapshot: SnapshotAssertion,
    error: str,
    messages: list[str],
    show_stack_trace: bool,
    translation_key: str,
) -> None:
    """Test component config error processing."""

    # Make sure the exception translation cache is loaded
    await async_setup_component(hass, "homeassistant", {})

    test_integration = Mock(
        domain="test_domain",
        documentation="https://example.com",
        get_platform=Mock(
            return_value=Mock(
                async_validate_config=AsyncMock(side_effect=ValueError("broken"))
            )
        ),
    )
    with (
        patch(
            "homeassistant.config.async_process_component_config",
            return_value=config_util.IntegrationConfigInfo(None, exception_info_list),
        ),
        pytest.raises(ConfigValidationError) as ex,
    ):
        await config_util.async_process_component_and_handle_errors(
            hass, {}, test_integration, raise_on_failure=True
        )
    records = [record for record in caplog.records if record.msg == messages[0]]
    assert len(records) == 1
    assert (records[0].exc_info is not None) == show_stack_trace
    assert str(ex.value) == snapshot
    assert ex.value.translation_key == translation_key
    assert ex.value.translation_domain == "homeassistant"
    assert ex.value.translation_placeholders["domain"] == "test_domain"
    assert all(message in caplog.text for message in messages)

    caplog.clear()
    with patch(
        "homeassistant.config.async_process_component_config",
        return_value=config_util.IntegrationConfigInfo(None, exception_info_list),
    ):
        await config_util.async_process_component_and_handle_errors(
            hass, ConfigTestClass({}), test_integration
        )
    assert all(message in caplog.text for message in messages)


@pytest.mark.parametrize(
    ("domain", "schema", "expected"),
    [
        ("zone", vol.Schema({vol.Optional("zone", default=list): [int]}), "list"),
        ("zone", vol.Schema({vol.Optional("zone", default=[]): [int]}), "list"),
        (
            "zone",
            vol.Schema({vol.Optional("zone", default={}): {vol.Optional("hello"): 1}}),
            "dict",
        ),
        (
            "zone",
            vol.Schema(
                {vol.Optional("zone", default=dict): {vol.Optional("hello"): 1}}
            ),
            "dict",
        ),
        ("zone", vol.Schema({vol.Optional("zone"): int}), None),
        ("zone", vol.Schema({"zone": int}), None),
        (
            "not_existing",
            vol.Schema({vol.Optional("zone", default=dict): dict}),
            None,
        ),
        ("non_existing", vol.Schema({"zone": int}), None),
        ("zone", vol.Schema({}), None),
        ("plex", vol.Schema(vol.All({"plex": {"host": str}})), "dict"),
        ("openuv", cv.deprecated("openuv"), None),
    ],
)
def test_identify_config_schema(domain, schema, expected) -> None:
    """Test identify config schema."""
    assert (
        config_util._identify_config_schema(Mock(DOMAIN=domain, CONFIG_SCHEMA=schema))
        == expected
    )


async def test_core_config_schema_historic_currency(hass: HomeAssistant) -> None:
    """Test core config schema."""
    await config_util.async_process_ha_core_config(hass, {"currency": "LTT"})

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue("homeassistant", "historic_currency")
    assert issue
    assert issue.translation_placeholders == {"currency": "LTT"}


async def test_core_store_historic_currency(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test core config store."""
    core_data = {
        "data": {
            "currency": "LTT",
        },
        "key": "core.config",
        "version": 1,
        "minor_version": 1,
    }
    hass_storage["core.config"] = dict(core_data)
    await config_util.async_process_ha_core_config(hass, {})

    issue_registry = ir.async_get(hass)
    issue_id = "historic_currency"
    issue = issue_registry.async_get_issue("homeassistant", issue_id)
    assert issue
    assert issue.translation_placeholders == {"currency": "LTT"}

    await hass.config.async_update(currency="EUR")
    issue = issue_registry.async_get_issue("homeassistant", issue_id)
    assert not issue


async def test_core_config_schema_no_country(hass: HomeAssistant) -> None:
    """Test core config schema."""
    await config_util.async_process_ha_core_config(hass, {})

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue("homeassistant", "country_not_configured")
    assert issue


@pytest.mark.parametrize(
    ("config", "expected_issue"),
    [
        ({}, None),
        ({"legacy_templates": True}, "legacy_templates_true"),
        ({"legacy_templates": False}, "legacy_templates_false"),
    ],
)
async def test_core_config_schema_legacy_template(
    hass: HomeAssistant, config: dict[str, Any], expected_issue: str | None
) -> None:
    """Test legacy_template core config schema."""
    await config_util.async_process_ha_core_config(hass, config)

    issue_registry = ir.async_get(hass)
    for issue_id in ("legacy_templates_true", "legacy_templates_false"):
        issue = issue_registry.async_get_issue("homeassistant", issue_id)
        assert issue if issue_id == expected_issue else not issue

    await config_util.async_process_ha_core_config(hass, {})
    for issue_id in ("legacy_templates_true", "legacy_templates_false"):
        assert not issue_registry.async_get_issue("homeassistant", issue_id)


async def test_core_store_no_country(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test core config store."""
    core_data = {
        "data": {},
        "key": "core.config",
        "version": 1,
        "minor_version": 1,
    }
    hass_storage["core.config"] = dict(core_data)
    await config_util.async_process_ha_core_config(hass, {})

    issue_registry = ir.async_get(hass)
    issue_id = "country_not_configured"
    issue = issue_registry.async_get_issue("homeassistant", issue_id)
    assert issue

    await hass.config.async_update(country="SE")
    issue = issue_registry.async_get_issue("homeassistant", issue_id)
    assert not issue


async def test_safe_mode(hass: HomeAssistant) -> None:
    """Test safe mode."""
    assert config_util.safe_mode_enabled(hass.config.config_dir) is False
    assert config_util.safe_mode_enabled(hass.config.config_dir) is False
    await config_util.async_enable_safe_mode(hass)
    assert config_util.safe_mode_enabled(hass.config.config_dir) is True
    assert config_util.safe_mode_enabled(hass.config.config_dir) is False


@pytest.mark.parametrize(
    "config_dir",
    [
        "basic",
        "basic_include",
        "include_dir_list",
        "include_dir_merge_list",
        "packages",
        "packages_include_dir_named",
    ],
)
async def test_component_config_validation_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    config_dir: str,
    mock_iot_domain_integration: Integration,
    mock_non_adr_0007_integration: None,
    mock_adr_0007_integrations: list[Integration],
    mock_custom_validator_integrations: list[Integration],
    snapshot: SnapshotAssertion,
) -> None:
    """Test schema error in component."""

    base_path = os.path.dirname(__file__)
    hass.config.config_dir = os.path.join(
        base_path, "fixtures", "core", "config", "component_validation", config_dir
    )
    config = await config_util.async_hass_config_yaml(hass)

    for domain_with_label in config:
        integration = await async_get_integration(
            hass, cv.domain_key(domain_with_label)
        )
        await config_util.async_process_component_and_handle_errors(
            hass,
            config,
            integration=integration,
        )

    error_records = [
        {
            "message": record.message,
            "has_exc_info": bool(record.exc_info),
        }
        for record in caplog.get_records("call")
        if record.levelno == logging.ERROR
    ]
    assert error_records == snapshot


@pytest.mark.parametrize(
    "config_dir",
    [
        "basic",
    ],
)
async def test_component_config_validation_error_with_docs(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    config_dir: str,
    mock_iot_domain_integration_with_docs: Integration,
    mock_non_adr_0007_integration_with_docs: None,
    mock_adr_0007_integrations_with_docs: list[Integration],
    mock_custom_validator_integrations_with_docs: list[Integration],
    snapshot: SnapshotAssertion,
) -> None:
    """Test schema error in component."""

    base_path = os.path.dirname(__file__)
    hass.config.config_dir = os.path.join(
        base_path, "fixtures", "core", "config", "component_validation", config_dir
    )
    config = await config_util.async_hass_config_yaml(hass)

    for domain_with_label in config:
        integration = await async_get_integration(
            hass, cv.domain_key(domain_with_label)
        )
        await config_util.async_process_component_and_handle_errors(
            hass,
            config,
            integration=integration,
        )

    error_records = [
        record.message
        for record in caplog.get_records("call")
        if record.levelno == logging.ERROR
    ]
    assert error_records == snapshot


@pytest.mark.parametrize(
    "config_dir",
    ["packages", "packages_include_dir_named"],
)
async def test_package_merge_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    config_dir: str,
    mock_iot_domain_integration: Integration,
    mock_non_adr_0007_integration: None,
    mock_adr_0007_integrations: list[Integration],
    snapshot: SnapshotAssertion,
) -> None:
    """Test schema error in component."""
    base_path = os.path.dirname(__file__)
    hass.config.config_dir = os.path.join(
        base_path, "fixtures", "core", "config", "package_errors", config_dir
    )
    await config_util.async_hass_config_yaml(hass)

    error_records = [
        record.message
        for record in caplog.get_records("call")
        if record.levelno == logging.ERROR
    ]
    assert error_records == snapshot


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError("No such file or directory: b'liblibc.a'"),
        ImportError(
            ("ModuleNotFoundError: No module named 'not_installed_something'"),
            name="not_installed_something",
        ),
    ],
)
@pytest.mark.parametrize(
    "config_dir",
    ["packages", "packages_include_dir_named"],
)
async def test_package_merge_exception(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    config_dir: str,
    error: Exception,
    snapshot: SnapshotAssertion,
) -> None:
    """Test exception when merging packages."""
    base_path = os.path.dirname(__file__)
    hass.config.config_dir = os.path.join(
        base_path, "fixtures", "core", "config", "package_exceptions", config_dir
    )
    with patch(
        "homeassistant.config.async_get_integration_with_requirements",
        side_effect=error,
    ):
        await config_util.async_hass_config_yaml(hass)

    error_records = [
        record.message
        for record in caplog.get_records("call")
        if record.levelno == logging.ERROR
    ]
    assert error_records == snapshot


@pytest.mark.parametrize(
    "config_dir",
    [
        "basic",
        "basic_include",
        "include_dir_list",
        "include_dir_merge_list",
        "packages_include_dir_named",
    ],
)
async def test_yaml_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    config_dir: str,
    mock_iot_domain_integration: Integration,
    mock_non_adr_0007_integration: None,
    mock_adr_0007_integrations: list[Integration],
    snapshot: SnapshotAssertion,
) -> None:
    """Test schema error in component."""

    base_path = os.path.dirname(__file__)
    hass.config.config_dir = os.path.join(
        base_path, "fixtures", "core", "config", "yaml_errors", config_dir
    )
    with pytest.raises(HomeAssistantError) as exc_info:
        await config_util.async_hass_config_yaml(hass)
    assert str(exc_info.value).replace(base_path, "<BASE_PATH>") == snapshot

    error_records = [
        record.message.replace(base_path, "<BASE_PATH>")
        for record in caplog.get_records("call")
        if record.levelno == logging.ERROR
    ]
    assert error_records == snapshot


@pytest.mark.parametrize(
    "config_dir",
    [
        "packages_dict",
        "packages_slug",
        "packages_include_dir_named_dict",
        "packages_include_dir_named_slug",
    ],
)
async def test_individual_packages_schema_validation_errors(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    config_dir: str,
    mock_iot_domain_integration: Integration,
    snapshot: SnapshotAssertion,
) -> None:
    """Tests syntactic errors in individual packages."""

    base_path = os.path.dirname(__file__)
    hass.config.config_dir = os.path.join(
        base_path, "fixtures", "core", "config", "package_schema_validation", config_dir
    )

    config = await config_util.async_hass_config_yaml(hass)

    error_records = [
        record.message
        for record in caplog.get_records("call")
        if record.levelno == logging.ERROR
    ]
    assert error_records == snapshot

    assert len(config["iot_domain"]) == 1


@pytest.mark.parametrize(
    "config_dir",
    [
        "packages_is_a_list",
        "packages_is_a_value",
        "packages_is_null",
    ],
)
async def test_packages_schema_validation_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    config_dir: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Ensure that global package schema validation errors are logged."""

    base_path = os.path.dirname(__file__)
    hass.config.config_dir = os.path.join(
        base_path,
        "fixtures",
        "core",
        "config",
        "package_schema_errors",
        config_dir,
    )

    config = await config_util.async_hass_config_yaml(hass)

    error_records = [
        record.message
        for record in caplog.get_records("call")
        if record.levelno == logging.ERROR
    ]
    assert error_records == snapshot

    assert len(config[HA_DOMAIN][config_util.CONF_PACKAGES]) == 0


def test_extract_domain_configs() -> None:
    """Test the extraction of domain configuration."""
    config = {
        "zone": None,
        "zoner": None,
        "zone ": None,
        "zone Hallo": None,
        "zone 100": None,
    }

    assert {"zone", "zone Hallo", "zone 100"} == set(
        config_util.extract_domain_configs(config, "zone")
    )


def test_config_per_platform() -> None:
    """Test config per platform method."""
    config = OrderedDict(
        [
            ("zone", {"platform": "hello"}),
            ("zoner", None),
            ("zone Hallo", [1, {"platform": "hello 2"}]),
            ("zone 100", None),
        ]
    )

    assert [
        ("hello", config["zone"]),
        (None, 1),
        ("hello 2", config["zone Hallo"][1]),
    ] == list(config_util.config_per_platform(config, "zone"))


def test_extract_platform_integrations() -> None:
    """Test extract_platform_integrations."""
    config = OrderedDict(
        [
            (b"zone", {"platform": "not str"}),
            ("zone", {"platform": "hello"}),
            ("switch", {"platform": ["un", "hash", "able"]}),
            ("zonex", []),
            ("zoney", ""),
            ("notzone", {"platform": "nothello"}),
            ("zoner", None),
            ("zone Hallo", [1, {"platform": "hello 2"}]),
            ("zone 100", None),
            ("i n v a-@@", None),
            ("i n v a-@@", {"platform": "hello"}),
            ("zoneq", "pig"),
            ("zoneempty", {"platform": ""}),
        ]
    )
    assert config_util.extract_platform_integrations(config, {"zone"}) == {
        "zone": {"hello", "hello 2"}
    }
    assert config_util.extract_platform_integrations(config, {"switch"}) == {}
    assert config_util.extract_platform_integrations(config, {"zonex"}) == {}
    assert config_util.extract_platform_integrations(config, {"zoney"}) == {}
    assert config_util.extract_platform_integrations(
        config, {"zone", "not_valid", "notzone"}
    ) == {"zone": {"hello 2", "hello"}, "notzone": {"nothello"}}
    assert config_util.extract_platform_integrations(config, {"zoneq"}) == {}
    assert config_util.extract_platform_integrations(config, {"zoneempty"}) == {}


@pytest.mark.parametrize("load_registries", [False])
async def test_loading_platforms_gathers(hass: HomeAssistant) -> None:
    """Test loading platform integrations gathers."""

    mock_integration(
        hass,
        MockModule(
            domain="platform_int",
        ),
    )
    mock_integration(
        hass,
        MockModule(
            domain="platform_int2",
        ),
    )

    # Its important that we do not mock the platforms with mock_platform
    # as the loader is smart enough to know they are already loaded and
    # will not create an executor job to load them. We are testing in
    # what order the executor jobs happen here as we want to make
    # sure the platform integrations are at the front of the line
    light_integration = await loader.async_get_integration(hass, "light")
    sensor_integration = await loader.async_get_integration(hass, "sensor")

    order: list[tuple[str, str]] = []

    def _load_platform(self, platform: str) -> MockModule:
        order.append((self.domain, platform))
        return MockModule()

    # We need to patch what runs in the executor so we are counting
    # the order that jobs are scheduled in th executor
    with patch(
        "homeassistant.loader.Integration._load_platform",
        _load_platform,
    ):
        light_task = hass.async_create_task(
            config.async_process_component_config(
                hass,
                {
                    "light": [
                        {"platform": "platform_int"},
                        {"platform": "platform_int2"},
                    ]
                },
                light_integration,
            ),
            eager_start=True,
        )
        sensor_task = hass.async_create_task(
            config.async_process_component_config(
                hass,
                {
                    "sensor": [
                        {"platform": "platform_int"},
                        {"platform": "platform_int2"},
                    ]
                },
                sensor_integration,
            ),
            eager_start=True,
        )

        await asyncio.gather(light_task, sensor_task)

    # Should be called in order so that
    # all the light platforms are imported
    # before the sensor platforms
    assert order == [
        ("platform_int", "light"),
        ("platform_int2", "light"),
        ("platform_int", "sensor"),
        ("platform_int2", "sensor"),
    ]
