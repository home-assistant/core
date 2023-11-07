"""Test check_config script."""
from unittest.mock import patch

import pytest

from homeassistant.config import YAML_CONFIG_FILE
import homeassistant.scripts.check_config as check_config

from tests.common import get_test_config_dir

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
async def apply_stop_hass(stop_hass: None) -> None:
    """Make sure all hass are stopped."""


@pytest.fixture
def mock_is_file():
    """Mock is_file."""
    # All files exist except for the old entity registry file
    with patch(
        "os.path.isfile", lambda path: not path.endswith("entity_registry.yaml")
    ):
        yield


def normalize_yaml_files(check_dict):
    """Remove configuration path from ['yaml_files']."""
    root = get_test_config_dir()
    return [key.replace(root, "...") for key in sorted(check_dict["yaml_files"].keys())]


@pytest.mark.parametrize("hass_config_yaml", [BAD_CORE_CONFIG])
def test_bad_core_config(mock_is_file, event_loop, mock_hass_config_yaml: None) -> None:
    """Test a bad core config setup."""
    res = check_config.check(get_test_config_dir())
    assert res["except"].keys() == {"homeassistant"}
    assert res["except"]["homeassistant"][1] == {"unit_system": "bad"}
    assert res["warn"] == {}


@pytest.mark.parametrize("hass_config_yaml", [BASE_CONFIG + "light:\n  platform: demo"])
def test_config_platform_valid(
    mock_is_file, event_loop, mock_hass_config_yaml: None
) -> None:
    """Test a valid platform setup."""
    res = check_config.check(get_test_config_dir())
    assert res["components"].keys() == {"homeassistant", "light"}
    assert res["components"]["light"] == [{"platform": "demo"}]
    assert res["except"] == {}
    assert res["secret_cache"] == {}
    assert res["secrets"] == {}
    assert res["warn"] == {}
    assert len(res["yaml_files"]) == 1


@pytest.mark.parametrize(
    ("hass_config_yaml", "platforms", "error"),
    [
        (
            BASE_CONFIG + "beer:",
            {"homeassistant"},
            "Integration error: beer - Integration 'beer' not found.",
        ),
        (
            BASE_CONFIG + "light:\n  platform: beer",
            {"homeassistant", "light"},
            "Platform error light.beer - Integration 'beer' not found.",
        ),
    ],
)
def test_component_platform_not_found(
    mock_is_file, event_loop, mock_hass_config_yaml: None, platforms, error
) -> None:
    """Test errors if component or platform not found."""
    # Make sure they don't exist
    res = check_config.check(get_test_config_dir())
    assert res["components"].keys() == platforms
    assert res["except"] == {}
    assert res["secret_cache"] == {}
    assert res["secrets"] == {}
    assert res["warn"] == {check_config.WARNING_STR: [error]}
    assert len(res["yaml_files"]) == 1


@pytest.mark.parametrize(
    "hass_config_yaml_files",
    [
        {
            get_test_config_dir(YAML_CONFIG_FILE): BASE_CONFIG
            + "http:\n  cors_allowed_origins: !secret http_pw",
            get_test_config_dir(
                "secrets.yaml"
            ): "logger: debug\nhttp_pw: http://google.com",
        }
    ],
)
def test_secrets(mock_is_file, event_loop, mock_hass_config_yaml: None) -> None:
    """Test secrets config checking method."""
    res = check_config.check(get_test_config_dir(), True)

    assert res["except"] == {}
    assert res["components"].keys() == {"homeassistant", "http"}
    assert res["components"]["http"] == {
        "cors_allowed_origins": ["http://google.com"],
        "ip_ban_enabled": True,
        "login_attempts_threshold": -1,
        "server_port": 8123,
        "ssl_profile": "modern",
        "use_x_frame_options": True,
    }
    assert res["secret_cache"] == {
        get_test_config_dir("secrets.yaml"): {"http_pw": "http://google.com"}
    }
    assert res["secrets"] == {"http_pw": "http://google.com"}
    assert res["warn"] == {}
    assert normalize_yaml_files(res) == [
        ".../configuration.yaml",
        ".../secrets.yaml",
    ]


@pytest.mark.parametrize(
    "hass_config_yaml", [BASE_CONFIG + '  packages:\n    p1:\n      group: ["a"]']
)
def test_package_invalid(mock_is_file, event_loop, mock_hass_config_yaml: None) -> None:
    """Test an invalid package."""
    res = check_config.check(get_test_config_dir())

    assert res["except"] == {}
    assert res["components"].keys() == {"homeassistant"}
    assert res["secret_cache"] == {}
    assert res["secrets"] == {}
    assert res["warn"].keys() == {"homeassistant.packages.p1.group"}
    assert res["warn"]["homeassistant.packages.p1.group"][1] == {"group": ["a"]}
    assert len(res["yaml_files"]) == 1


@pytest.mark.parametrize(
    "hass_config_yaml", [BASE_CONFIG + "automation: !include no.yaml"]
)
def test_bootstrap_error(event_loop, mock_hass_config_yaml: None) -> None:
    """Test a valid platform setup."""
    res = check_config.check(get_test_config_dir(YAML_CONFIG_FILE))
    err = res["except"].pop(check_config.ERROR_STR)
    assert len(err) == 1
    assert res["except"] == {}
    assert res["components"] == {}  # No components, load failed
    assert res["secret_cache"] == {}
    assert res["secrets"] == {}
    assert res["warn"] == {}
    assert res["yaml_files"] == {}
