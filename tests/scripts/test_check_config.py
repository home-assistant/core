"""Test check_config script."""
from unittest.mock import patch

import pytest

from homeassistant.config import YAML_CONFIG_FILE
import homeassistant.scripts.check_config as check_config

from tests.common import get_test_config_dir, patch_yaml_files

BASE_CONFIG = (
    "homeassistant:\n"
    "  name: Home\n"
    "  latitude: -26.107361\n"
    "  longitude: 28.054500\n"
    "  elevation: 1600\n"
    "  unit_system: metric\n"
    "  time_zone: GMT\n"
    "\n\n"
)

BAD_CORE_CONFIG = "homeassistant:\n  unit_system: bad\n\n\n"


@pytest.fixture(autouse=True)
async def apply_stop_hass(stop_hass):
    """Make sure all hass are stopped."""


def normalize_yaml_files(check_dict):
    """Remove configuration path from ['yaml_files']."""
    root = get_test_config_dir()
    return [key.replace(root, "...") for key in sorted(check_dict["yaml_files"].keys())]


@patch("os.path.isfile", return_value=True)
def test_bad_core_config(isfile_patch, loop):
    """Test a bad core config setup."""
    files = {YAML_CONFIG_FILE: BAD_CORE_CONFIG}
    with patch_yaml_files(files):
        res = check_config.check(get_test_config_dir())
        assert res["except"].keys() == {"homeassistant"}
        assert res["except"]["homeassistant"][1] == {"unit_system": "bad"}


@patch("os.path.isfile", return_value=True)
def test_config_platform_valid(isfile_patch, loop):
    """Test a valid platform setup."""
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "light:\n  platform: demo"}
    with patch_yaml_files(files):
        res = check_config.check(get_test_config_dir())
        assert res["components"].keys() == {"homeassistant", "light"}
        assert res["components"]["light"] == [{"platform": "demo"}]
        assert res["except"] == {}
        assert res["secret_cache"] == {}
        assert res["secrets"] == {}
        assert len(res["yaml_files"]) == 1


@patch("os.path.isfile", return_value=True)
def test_component_platform_not_found(isfile_patch, loop):
    """Test errors if component or platform not found."""
    # Make sure they don't exist
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "beer:"}
    with patch_yaml_files(files):
        res = check_config.check(get_test_config_dir())
        assert res["components"].keys() == {"homeassistant"}
        assert res["except"] == {
            check_config.ERROR_STR: [
                "Component error: beer - Integration 'beer' not found."
            ]
        }
        assert res["secret_cache"] == {}
        assert res["secrets"] == {}
        assert len(res["yaml_files"]) == 1

    files = {YAML_CONFIG_FILE: BASE_CONFIG + "light:\n  platform: beer"}
    with patch_yaml_files(files):
        res = check_config.check(get_test_config_dir())
        assert res["components"].keys() == {"homeassistant", "light"}
        assert res["components"]["light"] == []
        assert res["except"] == {
            check_config.ERROR_STR: [
                "Platform error light.beer - Integration 'beer' not found."
            ]
        }
        assert res["secret_cache"] == {}
        assert res["secrets"] == {}
        assert len(res["yaml_files"]) == 1


@patch("os.path.isfile", return_value=True)
def test_secrets(isfile_patch, loop):
    """Test secrets config checking method."""
    secrets_path = get_test_config_dir("secrets.yaml")

    files = {
        get_test_config_dir(YAML_CONFIG_FILE): BASE_CONFIG
        + ("http:\n  cors_allowed_origins: !secret http_pw"),
        secrets_path: ("logger: debug\nhttp_pw: http://google.com"),
    }

    with patch_yaml_files(files):

        res = check_config.check(get_test_config_dir(), True)

        assert res["except"] == {}
        assert res["components"].keys() == {"homeassistant", "http"}
        assert res["components"]["http"] == {
            "cors_allowed_origins": ["http://google.com"],
            "ip_ban_enabled": True,
            "login_attempts_threshold": -1,
            "server_port": 8123,
            "ssl_profile": "modern",
        }
        assert res["secret_cache"] == {secrets_path: {"http_pw": "http://google.com"}}
        assert res["secrets"] == {"http_pw": "http://google.com"}
        assert normalize_yaml_files(res) == [
            ".../configuration.yaml",
            ".../secrets.yaml",
        ]


@patch("os.path.isfile", return_value=True)
def test_package_invalid(isfile_patch, loop):
    """Test an invalid package."""
    files = {
        YAML_CONFIG_FILE: BASE_CONFIG + ("  packages:\n    p1:\n" '      group: ["a"]')
    }
    with patch_yaml_files(files):
        res = check_config.check(get_test_config_dir())

        assert res["except"].keys() == {"homeassistant.packages.p1.group"}
        assert res["except"]["homeassistant.packages.p1.group"][1] == {"group": ["a"]}
        assert len(res["except"]) == 1
        assert res["components"].keys() == {"homeassistant"}
        assert len(res["components"]) == 1
        assert res["secret_cache"] == {}
        assert res["secrets"] == {}
        assert len(res["yaml_files"]) == 1


def test_bootstrap_error(loop):
    """Test a valid platform setup."""
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "automation: !include no.yaml"}
    with patch_yaml_files(files):
        res = check_config.check(get_test_config_dir(YAML_CONFIG_FILE))
        err = res["except"].pop(check_config.ERROR_STR)
        assert len(err) == 1
        assert res["except"] == {}
        assert res["components"] == {}  # No components, load failed
        assert res["secret_cache"] == {}
        assert res["secrets"] == {}
        assert res["yaml_files"] == {}
