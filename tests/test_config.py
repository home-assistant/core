"""Test config utils."""
# pylint: disable=protected-access
import asyncio
from collections import OrderedDict
import copy
import os
from unittest import mock
from unittest.mock import Mock

import asynctest
from asynctest import CoroutineMock, patch
import pytest
import voluptuous as vol
from voluptuous import Invalid, MultipleInvalid
import yaml

import homeassistant.config as config_util
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_FRIENDLY_NAME,
    ATTR_HIDDEN,
    CONF_AUTH_MFA_MODULES,
    CONF_AUTH_PROVIDERS,
    CONF_CUSTOMIZE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_TEMPERATURE_UNIT,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
    __version__,
)
from homeassistant.core import SOURCE_STORAGE, HomeAssistantError
import homeassistant.helpers.check_config as check_config
from homeassistant.helpers.entity import Entity
from homeassistant.loader import async_get_integration
from homeassistant.util import dt as dt_util
from homeassistant.util.yaml import SECRET_YAML

from tests.common import get_test_config_dir, patch_yaml_files

CONFIG_DIR = get_test_config_dir()
YAML_PATH = os.path.join(CONFIG_DIR, config_util.YAML_CONFIG_FILE)
SECRET_PATH = os.path.join(CONFIG_DIR, SECRET_YAML)
VERSION_PATH = os.path.join(CONFIG_DIR, config_util.VERSION_FILE)
GROUP_PATH = os.path.join(CONFIG_DIR, config_util.GROUP_CONFIG_PATH)
AUTOMATIONS_PATH = os.path.join(CONFIG_DIR, config_util.AUTOMATION_CONFIG_PATH)
SCRIPTS_PATH = os.path.join(CONFIG_DIR, config_util.SCRIPT_CONFIG_PATH)
SCENES_PATH = os.path.join(CONFIG_DIR, config_util.SCENE_CONFIG_PATH)
ORIG_TIMEZONE = dt_util.DEFAULT_TIME_ZONE


def create_file(path):
    """Create an empty file."""
    with open(path, "w"):
        pass


def teardown():
    """Clean up."""
    dt_util.DEFAULT_TIME_ZONE = ORIG_TIMEZONE

    if os.path.isfile(YAML_PATH):
        os.remove(YAML_PATH)

    if os.path.isfile(SECRET_PATH):
        os.remove(SECRET_PATH)

    if os.path.isfile(VERSION_PATH):
        os.remove(VERSION_PATH)

    if os.path.isfile(GROUP_PATH):
        os.remove(GROUP_PATH)

    if os.path.isfile(AUTOMATIONS_PATH):
        os.remove(AUTOMATIONS_PATH)

    if os.path.isfile(SCRIPTS_PATH):
        os.remove(SCRIPTS_PATH)

    if os.path.isfile(SCENES_PATH):
        os.remove(SCENES_PATH)


async def test_create_default_config(hass):
    """Test creation of default config."""
    await config_util.async_create_default_config(hass)

    assert os.path.isfile(YAML_PATH)
    assert os.path.isfile(SECRET_PATH)
    assert os.path.isfile(VERSION_PATH)
    assert os.path.isfile(GROUP_PATH)
    assert os.path.isfile(AUTOMATIONS_PATH)


async def test_ensure_config_exists_creates_config(hass):
    """Test that calling ensure_config_exists.

    If not creates a new config file.
    """
    with mock.patch("builtins.print") as mock_print:
        await config_util.async_ensure_config_exists(hass)

    assert os.path.isfile(YAML_PATH)
    assert mock_print.called


async def test_ensure_config_exists_uses_existing_config(hass):
    """Test that calling ensure_config_exists uses existing config."""
    create_file(YAML_PATH)
    await config_util.async_ensure_config_exists(hass)

    with open(YAML_PATH) as f:
        content = f.read()

    # File created with create_file are empty
    assert content == ""


def test_load_yaml_config_converts_empty_files_to_dict():
    """Test that loading an empty file returns an empty dict."""
    create_file(YAML_PATH)

    assert isinstance(config_util.load_yaml_config_file(YAML_PATH), dict)


def test_load_yaml_config_raises_error_if_not_dict():
    """Test error raised when YAML file is not a dict."""
    with open(YAML_PATH, "w") as f:
        f.write("5")

    with pytest.raises(HomeAssistantError):
        config_util.load_yaml_config_file(YAML_PATH)


def test_load_yaml_config_raises_error_if_malformed_yaml():
    """Test error raised if invalid YAML."""
    with open(YAML_PATH, "w") as f:
        f.write(":")

    with pytest.raises(HomeAssistantError):
        config_util.load_yaml_config_file(YAML_PATH)


def test_load_yaml_config_raises_error_if_unsafe_yaml():
    """Test error raised if unsafe YAML."""
    with open(YAML_PATH, "w") as f:
        f.write("hello: !!python/object/apply:os.system")

    with pytest.raises(HomeAssistantError):
        config_util.load_yaml_config_file(YAML_PATH)


def test_load_yaml_config_preserves_key_order():
    """Test removal of library."""
    with open(YAML_PATH, "w") as f:
        f.write("hello: 2\n")
        f.write("world: 1\n")

    assert [("hello", 2), ("world", 1)] == list(
        config_util.load_yaml_config_file(YAML_PATH).items()
    )


async def test_create_default_config_returns_none_if_write_error(hass):
    """Test the writing of a default configuration.

    Non existing folder returns None.
    """
    hass.config.config_dir = os.path.join(CONFIG_DIR, "non_existing_dir/")
    with mock.patch("builtins.print") as mock_print:
        assert await config_util.async_create_default_config(hass) is False
    assert mock_print.called


def test_core_config_schema():
    """Test core config schema."""
    for value in (
        {CONF_UNIT_SYSTEM: "K"},
        {"time_zone": "non-exist"},
        {"latitude": "91"},
        {"longitude": -181},
        {"customize": "bla"},
        {"customize": {"light.sensor": 100}},
        {"customize": {"entity_id": []}},
    ):
        with pytest.raises(MultipleInvalid):
            config_util.CORE_CONFIG_SCHEMA(value)

    config_util.CORE_CONFIG_SCHEMA(
        {
            "name": "Test name",
            "latitude": "-23.45",
            "longitude": "123.45",
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
            "customize": {"sensor.temperature": {"hidden": True}},
        }
    )


def test_customize_dict_schema():
    """Test basic customize config validation."""
    values = ({ATTR_FRIENDLY_NAME: None}, {ATTR_HIDDEN: "2"}, {ATTR_ASSUMED_STATE: "2"})

    for val in values:
        print(val)
        with pytest.raises(MultipleInvalid):
            config_util.CUSTOMIZE_DICT_SCHEMA(val)

    assert config_util.CUSTOMIZE_DICT_SCHEMA(
        {ATTR_FRIENDLY_NAME: 2, ATTR_HIDDEN: "1", ATTR_ASSUMED_STATE: "0"}
    ) == {ATTR_FRIENDLY_NAME: "2", ATTR_HIDDEN: True, ATTR_ASSUMED_STATE: False}


def test_customize_glob_is_ordered():
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


async def test_entity_customization(hass):
    """Test entity customization through configuration."""
    config = {
        CONF_LATITUDE: 50,
        CONF_LONGITUDE: 50,
        CONF_NAME: "Test",
        CONF_CUSTOMIZE: {"test.test": {"hidden": True}},
    }

    state = await _compute_state(hass, config)

    assert state.attributes["hidden"]


@mock.patch("homeassistant.config.shutil")
@mock.patch("homeassistant.config.os")
@mock.patch("homeassistant.config.is_docker_env", return_value=False)
def test_remove_lib_on_upgrade(mock_docker, mock_os, mock_shutil, hass):
    """Test removal of library on upgrade from before 0.50."""
    ha_version = "0.49.0"
    mock_os.path.isdir = mock.Mock(return_value=True)
    mock_open = mock.mock_open()
    with mock.patch("homeassistant.config.open", mock_open, create=True):
        opened_file = mock_open.return_value
        # pylint: disable=no-member
        opened_file.readline.return_value = ha_version
        hass.config.path = mock.Mock()
        config_util.process_ha_config_upgrade(hass)
        hass_path = hass.config.path.return_value

        assert mock_os.path.isdir.call_count == 1
        assert mock_os.path.isdir.call_args == mock.call(hass_path)
        assert mock_shutil.rmtree.call_count == 1
        assert mock_shutil.rmtree.call_args == mock.call(hass_path)


@mock.patch("homeassistant.config.shutil")
@mock.patch("homeassistant.config.os")
@mock.patch("homeassistant.config.is_docker_env", return_value=True)
def test_remove_lib_on_upgrade_94(mock_docker, mock_os, mock_shutil, hass):
    """Test removal of library on upgrade from before 0.94 and in Docker."""
    ha_version = "0.93.0.dev0"
    mock_os.path.isdir = mock.Mock(return_value=True)
    mock_open = mock.mock_open()
    with mock.patch("homeassistant.config.open", mock_open, create=True):
        opened_file = mock_open.return_value
        # pylint: disable=no-member
        opened_file.readline.return_value = ha_version
        hass.config.path = mock.Mock()
        config_util.process_ha_config_upgrade(hass)
        hass_path = hass.config.path.return_value

        assert mock_os.path.isdir.call_count == 1
        assert mock_os.path.isdir.call_args == mock.call(hass_path)
        assert mock_shutil.rmtree.call_count == 1
        assert mock_shutil.rmtree.call_args == mock.call(hass_path)


def test_process_config_upgrade(hass):
    """Test update of version on upgrade."""
    ha_version = "0.92.0"

    mock_open = mock.mock_open()
    with mock.patch(
        "homeassistant.config.open", mock_open, create=True
    ), mock.patch.object(config_util, "__version__", "0.91.0"):
        opened_file = mock_open.return_value
        # pylint: disable=no-member
        opened_file.readline.return_value = ha_version

        config_util.process_ha_config_upgrade(hass)

        assert opened_file.write.call_count == 1
        assert opened_file.write.call_args == mock.call("0.91.0")


def test_config_upgrade_same_version(hass):
    """Test no update of version on no upgrade."""
    ha_version = __version__

    mock_open = mock.mock_open()
    with mock.patch("homeassistant.config.open", mock_open, create=True):
        opened_file = mock_open.return_value
        # pylint: disable=no-member
        opened_file.readline.return_value = ha_version

        config_util.process_ha_config_upgrade(hass)

        assert opened_file.write.call_count == 0


def test_config_upgrade_no_file(hass):
    """Test update of version on upgrade, with no version file."""
    mock_open = mock.mock_open()
    mock_open.side_effect = [FileNotFoundError(), mock.DEFAULT, mock.DEFAULT]
    with mock.patch("homeassistant.config.open", mock_open, create=True):
        opened_file = mock_open.return_value
        # pylint: disable=no-member
        config_util.process_ha_config_upgrade(hass)
        assert opened_file.write.call_count == 1
        assert opened_file.write.call_args == mock.call(__version__)


async def test_loading_configuration_from_storage(hass, hass_storage):
    """Test loading core config onto hass object."""
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
        hass, {"whitelist_external_dirs": "/etc"}
    )

    assert hass.config.latitude == 55
    assert hass.config.longitude == 13
    assert hass.config.elevation == 10
    assert hass.config.location_name == "Home"
    assert hass.config.units.name == CONF_UNIT_SYSTEM_METRIC
    assert hass.config.time_zone.zone == "Europe/Copenhagen"
    assert len(hass.config.whitelist_external_dirs) == 2
    assert "/etc" in hass.config.whitelist_external_dirs
    assert hass.config.config_source == SOURCE_STORAGE


async def test_updating_configuration(hass, hass_storage):
    """Test updating configuration stores the new configuration."""
    core_data = {
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
    hass_storage["core.config"] = dict(core_data)
    await config_util.async_process_ha_core_config(
        hass, {"whitelist_external_dirs": "/etc"}
    )
    await hass.config.async_update(latitude=50)

    new_core_data = copy.deepcopy(core_data)
    new_core_data["data"]["latitude"] = 50
    assert hass_storage["core.config"] == new_core_data
    assert hass.config.latitude == 50


async def test_override_stored_configuration(hass, hass_storage):
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
        hass, {"latitude": 60, "whitelist_external_dirs": "/etc"}
    )

    assert hass.config.latitude == 60
    assert hass.config.longitude == 13
    assert hass.config.elevation == 10
    assert hass.config.location_name == "Home"
    assert hass.config.units.name == CONF_UNIT_SYSTEM_METRIC
    assert hass.config.time_zone.zone == "Europe/Copenhagen"
    assert len(hass.config.whitelist_external_dirs) == 2
    assert "/etc" in hass.config.whitelist_external_dirs
    assert hass.config.config_source == config_util.SOURCE_YAML


async def test_loading_configuration(hass):
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
            "whitelist_external_dirs": "/etc",
        },
    )

    assert hass.config.latitude == 60
    assert hass.config.longitude == 50
    assert hass.config.elevation == 25
    assert hass.config.location_name == "Huis"
    assert hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL
    assert hass.config.time_zone.zone == "America/New_York"
    assert len(hass.config.whitelist_external_dirs) == 2
    assert "/etc" in hass.config.whitelist_external_dirs
    assert hass.config.config_source == config_util.SOURCE_YAML


async def test_loading_configuration_temperature_unit(hass):
    """Test backward compatibility when loading core config."""
    await config_util.async_process_ha_core_config(
        hass,
        {
            "latitude": 60,
            "longitude": 50,
            "elevation": 25,
            "name": "Huis",
            CONF_TEMPERATURE_UNIT: "C",
            "time_zone": "America/New_York",
        },
    )

    assert hass.config.latitude == 60
    assert hass.config.longitude == 50
    assert hass.config.elevation == 25
    assert hass.config.location_name == "Huis"
    assert hass.config.units.name == CONF_UNIT_SYSTEM_METRIC
    assert hass.config.time_zone.zone == "America/New_York"
    assert hass.config.config_source == config_util.SOURCE_YAML


async def test_loading_configuration_from_packages(hass):
    """Test loading packages config onto hass object config."""
    await config_util.async_process_ha_core_config(
        hass,
        {
            "latitude": 39,
            "longitude": -1,
            "elevation": 500,
            "name": "Huis",
            CONF_TEMPERATURE_UNIT: "C",
            "time_zone": "Europe/Madrid",
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
                CONF_TEMPERATURE_UNIT: "C",
                "time_zone": "Europe/Madrid",
                "packages": {"empty_package": None},
            },
        )


@asynctest.mock.patch("homeassistant.helpers.check_config.async_check_ha_config_file")
async def test_check_ha_config_file_correct(mock_check, hass):
    """Check that restart propagates to stop."""
    mock_check.return_value = check_config.HomeAssistantConfig()
    assert await config_util.async_check_ha_config_file(hass) is None


@asynctest.mock.patch("homeassistant.helpers.check_config.async_check_ha_config_file")
async def test_check_ha_config_file_wrong(mock_check, hass):
    """Check that restart with a bad config doesn't propagate to stop."""
    mock_check.return_value = check_config.HomeAssistantConfig()
    mock_check.return_value.add_error("bad")

    assert await config_util.async_check_ha_config_file(hass) == "bad"


@asynctest.mock.patch(
    "homeassistant.config.os.path.isfile", mock.Mock(return_value=True)
)
async def test_async_hass_config_yaml_merge(merge_log_err, hass):
    """Test merge during async config reload."""
    config = {
        config_util.CONF_CORE: {
            config_util.CONF_PACKAGES: {"pack_dict": {"input_boolean": {"ib1": None}}}
        },
        "input_boolean": {"ib2": None},
        "light": {"platform": "test"},
    }

    files = {config_util.YAML_CONFIG_FILE: yaml.dump(config)}
    with patch_yaml_files(files, True):
        conf = await config_util.async_hass_config_yaml(hass)

    assert merge_log_err.call_count == 0
    assert conf[config_util.CONF_CORE].get(config_util.CONF_PACKAGES) is not None
    assert len(conf) == 3
    assert len(conf["input_boolean"]) == 2
    assert len(conf["light"]) == 1


# pylint: disable=redefined-outer-name
@pytest.fixture
def merge_log_err(hass):
    """Patch _merge_log_error from packages."""
    with mock.patch("homeassistant.config._LOGGER.error") as logerr:
        yield logerr


async def test_merge(merge_log_err, hass):
    """Test if we can merge packages."""
    packages = {
        "pack_dict": {"input_boolean": {"ib1": None}},
        "pack_11": {"input_select": {"is1": None}},
        "pack_list": {"light": {"platform": "test"}},
        "pack_list2": {"light": [{"platform": "test"}]},
        "pack_none": {"wake_on_lan": None},
    }
    config = {
        config_util.CONF_CORE: {config_util.CONF_PACKAGES: packages},
        "input_boolean": {"ib2": None},
        "light": {"platform": "test"},
    }
    await config_util.merge_packages_config(hass, config, packages)

    assert merge_log_err.call_count == 0
    assert len(config) == 5
    assert len(config["input_boolean"]) == 2
    assert len(config["input_select"]) == 1
    assert len(config["light"]) == 3
    assert isinstance(config["wake_on_lan"], OrderedDict)


async def test_merge_try_falsy(merge_log_err, hass):
    """Ensure we don't add falsy items like empty OrderedDict() to list."""
    packages = {
        "pack_falsy_to_lst": {"automation": OrderedDict()},
        "pack_list2": {"light": OrderedDict()},
    }
    config = {
        config_util.CONF_CORE: {config_util.CONF_PACKAGES: packages},
        "automation": {"do": "something"},
        "light": {"some": "light"},
    }
    await config_util.merge_packages_config(hass, config, packages)

    assert merge_log_err.call_count == 0
    assert len(config) == 3
    assert len(config["automation"]) == 1
    assert len(config["light"]) == 1


async def test_merge_new(merge_log_err, hass):
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
    config = {config_util.CONF_CORE: {config_util.CONF_PACKAGES: packages}}
    await config_util.merge_packages_config(hass, config, packages)

    assert merge_log_err.call_count == 0
    assert "api" in config
    assert len(config) == 5
    assert len(config["light"]) == 2
    assert len(config["panel_custom"]) == 1


async def test_merge_type_mismatch(merge_log_err, hass):
    """Test if we have a type mismatch for packages."""
    packages = {
        "pack_1": {"input_boolean": [{"ib1": None}]},
        "pack_11": {"input_select": {"ib1": None}},
        "pack_2": {"light": {"ib1": None}},  # light gets merged - ensure_list
    }
    config = {
        config_util.CONF_CORE: {config_util.CONF_PACKAGES: packages},
        "input_boolean": {"ib2": None},
        "input_select": [{"ib2": None}],
        "light": [{"platform": "two"}],
    }
    await config_util.merge_packages_config(hass, config, packages)

    assert merge_log_err.call_count == 2
    assert len(config) == 4
    assert len(config["input_boolean"]) == 1
    assert len(config["light"]) == 2


async def test_merge_once_only_keys(merge_log_err, hass):
    """Test if we have a merge for a comp that may occur only once. Keys."""
    packages = {"pack_2": {"api": None}}
    config = {config_util.CONF_CORE: {config_util.CONF_PACKAGES: packages}, "api": None}
    await config_util.merge_packages_config(hass, config, packages)
    assert config["api"] == OrderedDict()

    packages = {"pack_2": {"api": {"key_3": 3}}}
    config = {
        config_util.CONF_CORE: {config_util.CONF_PACKAGES: packages},
        "api": {"key_1": 1, "key_2": 2},
    }
    await config_util.merge_packages_config(hass, config, packages)
    assert config["api"] == {"key_1": 1, "key_2": 2, "key_3": 3}

    # Duplicate keys error
    packages = {"pack_2": {"api": {"key": 2}}}
    config = {
        config_util.CONF_CORE: {config_util.CONF_PACKAGES: packages},
        "api": {"key": 1},
    }
    await config_util.merge_packages_config(hass, config, packages)
    assert merge_log_err.call_count == 1


async def test_merge_once_only_lists(hass):
    """Test if we have a merge for a comp that may occur only once. Lists."""
    packages = {
        "pack_2": {
            "api": {"list_1": ["item_2", "item_3"], "list_2": ["item_4"], "list_3": []}
        }
    }
    config = {
        config_util.CONF_CORE: {config_util.CONF_PACKAGES: packages},
        "api": {"list_1": ["item_1"]},
    }
    await config_util.merge_packages_config(hass, config, packages)
    assert config["api"] == {
        "list_1": ["item_1", "item_2", "item_3"],
        "list_2": ["item_4"],
        "list_3": [],
    }


async def test_merge_once_only_dictionaries(hass):
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
        config_util.CONF_CORE: {config_util.CONF_PACKAGES: packages},
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


async def test_merge_id_schema(hass):
    """Test if we identify the config schemas correctly."""
    types = {
        "panel_custom": "list",
        "group": "dict",
        "script": "dict",
        "input_boolean": "dict",
        "shell_command": "dict",
        "qwikswitch": "dict",
    }
    for domain, expected_type in types.items():
        integration = await async_get_integration(hass, domain)
        module = integration.get_component()
        typ, _ = config_util._identify_config_schema(module)
        assert typ == expected_type, f"{domain} expected {expected_type}, got {typ}"


async def test_merge_duplicate_keys(merge_log_err, hass):
    """Test if keys in dicts are duplicates."""
    packages = {"pack_1": {"input_select": {"ib1": None}}}
    config = {
        config_util.CONF_CORE: {config_util.CONF_PACKAGES: packages},
        "input_select": {"ib1": 1},
    }
    await config_util.merge_packages_config(hass, config, packages)

    assert merge_log_err.call_count == 1
    assert len(config) == 2
    assert len(config["input_select"]) == 1


@asyncio.coroutine
def test_merge_customize(hass):
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
    yield from config_util.async_process_ha_core_config(hass, core_config)

    assert hass.data[config_util.DATA_CUSTOMIZE].get("b.b") == {"friendly_name": "BB"}


async def test_auth_provider_config(hass):
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


async def test_auth_provider_config_default(hass):
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


async def test_disallowed_auth_provider_config(hass):
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


async def test_disallowed_duplicated_auth_provider_config(hass):
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


async def test_disallowed_auth_mfa_module_config(hass):
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


async def test_disallowed_duplicated_auth_mfa_module_config(hass):
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


async def test_merge_split_component_definition(hass):
    """Test components with trailing description in packages are merged."""
    packages = {
        "pack_1": {"light one": {"l1": None}},
        "pack_2": {"light two": {"l2": None}, "light three": {"l3": None}},
    }
    config = {config_util.CONF_CORE: {config_util.CONF_PACKAGES: packages}}
    await config_util.merge_packages_config(hass, config, packages)

    assert len(config) == 4
    assert len(config["light one"]) == 1
    assert len(config["light two"]) == 1
    assert len(config["light three"]) == 1


async def test_component_config_exceptions(hass, caplog):
    """Test unexpected exceptions validating component config."""
    # Config validator
    assert (
        await config_util.async_process_component_config(
            hass,
            {},
            integration=Mock(
                domain="test_domain",
                get_platform=Mock(
                    return_value=Mock(
                        async_validate_config=CoroutineMock(
                            side_effect=ValueError("broken")
                        )
                    )
                ),
            ),
        )
        is None
    )
    assert "ValueError: broken" in caplog.text
    assert "Unknown error calling test_domain config validator" in caplog.text

    # component.CONFIG_SCHEMA
    caplog.clear()
    assert (
        await config_util.async_process_component_config(
            hass,
            {},
            integration=Mock(
                domain="test_domain",
                get_platform=Mock(return_value=None),
                get_component=Mock(
                    return_value=Mock(
                        CONFIG_SCHEMA=Mock(side_effect=ValueError("broken"))
                    )
                ),
            ),
        )
        is None
    )
    assert "ValueError: broken" in caplog.text
    assert "Unknown error calling test_domain CONFIG_SCHEMA" in caplog.text

    # component.PLATFORM_SCHEMA
    caplog.clear()
    assert await config_util.async_process_component_config(
        hass,
        {"test_domain": {"platform": "test_platform"}},
        integration=Mock(
            domain="test_domain",
            get_platform=Mock(return_value=None),
            get_component=Mock(
                return_value=Mock(
                    spec=["PLATFORM_SCHEMA_BASE"],
                    PLATFORM_SCHEMA_BASE=Mock(side_effect=ValueError("broken")),
                )
            ),
        ),
    ) == {"test_domain": []}
    assert "ValueError: broken" in caplog.text
    assert (
        "Unknown error validating test_platform platform config with test_domain component platform schema"
        in caplog.text
    )

    # platform.PLATFORM_SCHEMA
    caplog.clear()
    with patch(
        "homeassistant.config.async_get_integration_with_requirements",
        return_value=Mock(  # integration that owns platform
            get_platform=Mock(
                return_value=Mock(  # platform
                    PLATFORM_SCHEMA=Mock(side_effect=ValueError("broken"))
                )
            )
        ),
    ):
        assert await config_util.async_process_component_config(
            hass,
            {"test_domain": {"platform": "test_platform"}},
            integration=Mock(
                domain="test_domain",
                get_platform=Mock(return_value=None),
                get_component=Mock(return_value=Mock(spec=["PLATFORM_SCHEMA_BASE"])),
            ),
        ) == {"test_domain": []}
        assert "ValueError: broken" in caplog.text
        assert (
            "Unknown error validating config for test_platform platform for test_domain component with PLATFORM_SCHEMA"
            in caplog.text
        )


@pytest.mark.parametrize(
    "domain, schema, expected",
    [
        ("zone", vol.Schema({vol.Optional("zone", default=[]): list}), "list"),
        ("zone", vol.Schema({vol.Optional("zone", default=dict): dict}), "dict"),
    ],
)
def test_identify_config_schema(domain, schema, expected):
    """Test identify config schema."""
    assert (
        config_util._identify_config_schema(Mock(DOMAIN=domain, CONFIG_SCHEMA=schema))[
            0
        ]
        == expected
    )
