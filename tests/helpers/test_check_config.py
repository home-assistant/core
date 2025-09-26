"""Test check_config helper."""

import logging
from unittest.mock import Mock, patch

import pytest
import voluptuous as vol

from homeassistant.config import YAML_CONFIG_FILE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.check_config import (
    CheckConfigError,
    HomeAssistantConfig,
    async_check_ha_config_file,
)
from homeassistant.requirements import RequirementsNotFound

from tests.common import (
    MockModule,
    MockPlatform,
    mock_integration,
    mock_platform,
    patch_yaml_files,
)

_LOGGER = logging.getLogger(__name__)

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


def log_ha_config(conf):
    """Log the returned config."""
    _LOGGER.debug("CONFIG - %s lines - %s errors", len(conf), len(conf.errors))
    for cnt, (key, val) in enumerate(conf.items()):
        _LOGGER.debug("#%s - %s: %s", cnt + 1, key, val)
    for cnt, err in enumerate(conf.errors):
        _LOGGER.debug("error[%s] = %s", cnt, err)


def _assert_warnings_errors(
    res: HomeAssistantConfig,
    expected_warnings: list[CheckConfigError],
    expected_errors: list[CheckConfigError],
) -> None:
    assert len(res.warnings) == len(expected_warnings)
    assert len(res.errors) == len(expected_errors)

    expected_warning_str = ""
    expected_error_str = ""

    for idx, expected_warning in enumerate(expected_warnings):
        assert res.warnings[idx] == expected_warning
        expected_warning_str += expected_warning.message
    assert res.warning_str == expected_warning_str

    for idx, expected_error in enumerate(expected_errors):
        assert res.errors[idx] == expected_error
        expected_error_str += expected_error.message
    assert res.error_str == expected_error_str


async def test_bad_core_config(hass: HomeAssistant) -> None:
    """Test a bad core config setup."""
    files = {YAML_CONFIG_FILE: BAD_CORE_CONFIG}
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        error = CheckConfigError(
            (
                f"Invalid config for 'homeassistant' at {YAML_CONFIG_FILE}, line 2:"
                " not a valid value for dictionary value 'unit_system', got 'bad'"
            ),
            "homeassistant",
            {"unit_system": "bad"},
        )
        _assert_warnings_errors(res, [], [error])


async def test_config_platform_valid(hass: HomeAssistant) -> None:
    """Test a valid platform setup."""
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "light:\n  platform: demo"}
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.keys() == {"homeassistant", "light"}
        assert res["light"] == [{"platform": "demo"}]
        _assert_warnings_errors(res, [], [])


async def test_integration_not_found(hass: HomeAssistant) -> None:
    """Test errors if integration not found."""
    # Make sure they don't exist
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "beer:"}
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.keys() == {"homeassistant"}
        warning = CheckConfigError(
            "Integration error: beer - Integration 'beer' not found.", None, None
        )
        _assert_warnings_errors(res, [warning], [])


async def test_integrationt_requirement_not_found(hass: HomeAssistant) -> None:
    """Test errors if integration with a requirement not found not found."""
    # Make sure they don't exist
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "test_custom_component:"}
    with (
        patch(
            "homeassistant.helpers.check_config.async_get_integration_with_requirements",
            side_effect=RequirementsNotFound("test_custom_component", ["any"]),
        ),
        patch("os.path.isfile", return_value=True),
        patch_yaml_files(files),
    ):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.keys() == {"homeassistant"}
        warning = CheckConfigError(
            (
                "Integration error: test_custom_component - Requirements for"
                " test_custom_component not found: ['any']."
            ),
            None,
            None,
        )
        _assert_warnings_errors(res, [warning], [])


async def test_integration_not_found_recovery_mode(hass: HomeAssistant) -> None:
    """Test no errors if integration not found in recovery mode."""
    # Make sure they don't exist
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "beer:"}
    hass.config.recovery_mode = True
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.keys() == {"homeassistant"}
        _assert_warnings_errors(res, [], [])


async def test_integration_not_found_safe_mode(hass: HomeAssistant) -> None:
    """Test no errors if integration not found in safe mode."""
    # Make sure they don't exist
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "beer:"}
    hass.config.safe_mode = True
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.keys() == {"homeassistant"}
        _assert_warnings_errors(res, [], [])


async def test_integration_import_error(hass: HomeAssistant) -> None:
    """Test errors if integration with a requirement not found not found."""
    # Make sure they don't exist
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "light:"}
    with (
        patch(
            "homeassistant.loader.Integration.async_get_component",
            side_effect=ImportError("blablabla"),
        ),
        patch("os.path.isfile", return_value=True),
        patch_yaml_files(files),
    ):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.keys() == {"homeassistant"}
        warning = CheckConfigError(
            "Component error: light - blablabla",
            None,
            None,
        )
        _assert_warnings_errors(res, [warning], [])


@pytest.mark.parametrize(
    ("integration", "errors", "warnings", "message"),
    [
        ("frontend", 1, 0, "'blah' is an invalid option for 'frontend'"),
        ("http", 1, 0, "'blah' is an invalid option for 'http'"),
        ("logger", 0, 1, "'blah' is an invalid option for 'logger'"),
    ],
)
async def test_integration_schema_error(
    hass: HomeAssistant, integration: str, errors: int, warnings: int, message: str
) -> None:
    """Test schema error in integration."""
    # Make sure they don't exist
    files = {YAML_CONFIG_FILE: BASE_CONFIG + f"frontend:\n{integration}:\n    blah:"}
    hass.config.safe_mode = True
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert len(res.errors) == errors
        assert len(res.warnings) == warnings

        for err in res.errors:
            assert message in err.message
        for warn in res.warnings:
            assert message in warn.message


async def test_platform_not_found(hass: HomeAssistant) -> None:
    """Test errors if platform not found."""
    # Make sure they don't exist
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "light:\n  platform: beer"}
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.keys() == {"homeassistant", "light"}
        assert res["light"] == []

        warning = CheckConfigError(
            (
                "Platform error 'light' from integration 'beer' - "
                "Integration 'beer' not found."
            ),
            None,
            None,
        )
        _assert_warnings_errors(res, [warning], [])


async def test_platform_not_found_recovery_mode(hass: HomeAssistant) -> None:
    """Test no errors if platform not found in recovery mode."""
    # Make sure they don't exist
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "light:\n  platform: beer"}
    hass.config.recovery_mode = True
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.keys() == {"homeassistant", "light"}
        assert res["light"] == []

        _assert_warnings_errors(res, [], [])


async def test_platform_not_found_safe_mode(hass: HomeAssistant) -> None:
    """Test no errors if platform not found in safe mode."""
    # Make sure they don't exist
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "light:\n  platform: beer"}
    hass.config.safe_mode = True
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.keys() == {"homeassistant", "light"}
        assert res["light"] == []

        _assert_warnings_errors(res, [], [])


@pytest.mark.parametrize(
    ("extra_config", "warnings", "message", "config"),
    [
        (
            "blah:\n  - platform: test\n    option1: abc",
            0,
            None,
            None,
        ),
        (
            "blah:\n  - platform: test\n    option1: 123",
            1,
            "expected str for dictionary value",
            {"option1": 123, "platform": "test"},
        ),
        # Test the attached config is unvalidated (key old is removed by validator)
        (
            "blah:\n  - platform: test\n    old: blah\n    option1: 123",
            1,
            "expected str for dictionary value",
            {"old": "blah", "option1": 123, "platform": "test"},
        ),
        # Test base platform configuration error
        (
            "blah:\n  - paltfrom: test\n",
            1,
            "required key 'platform' not provided",
            {"paltfrom": "test"},
        ),
    ],
)
async def test_platform_schema_error(
    hass: HomeAssistant,
    extra_config: str,
    warnings: int,
    message: str | None,
    config: dict | None,
) -> None:
    """Test schema error in platform."""
    comp_platform_schema = cv.PLATFORM_SCHEMA.extend({vol.Remove("old"): str})
    comp_platform_schema_base = comp_platform_schema.extend({}, extra=vol.ALLOW_EXTRA)
    mock_integration(
        hass,
        MockModule("blah", platform_schema_base=comp_platform_schema_base),
    )
    test_platform_schema = comp_platform_schema.extend({"option1": str})
    mock_platform(
        hass,
        "test.blah",
        MockPlatform(platform_schema=test_platform_schema),
    )

    files = {YAML_CONFIG_FILE: BASE_CONFIG + extra_config}
    hass.config.safe_mode = True
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert len(res.errors) == 0
        assert len(res.warnings) == warnings

        for warn in res.warnings:
            assert message in warn.message
            assert warn.config == config


async def test_config_platform_import_error(hass: HomeAssistant) -> None:
    """Test errors if config platform fails to import."""
    # Make sure they don't exist
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "light:\n  platform: beer"}
    with (
        patch(
            "homeassistant.loader.Integration.async_get_platform",
            side_effect=ImportError("blablabla"),
        ),
        patch("os.path.isfile", return_value=True),
        patch("homeassistant.loader.Integration.platforms_exists", return_value=True),
        patch_yaml_files(files),
    ):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.keys() == {"homeassistant"}
        error = CheckConfigError(
            "Error importing config platform light: blablabla",
            None,
            None,
        )
        _assert_warnings_errors(res, [], [error])


async def test_platform_import_error(hass: HomeAssistant) -> None:
    """Test errors if platform not found."""
    # Make sure they don't exist
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "light:\n  platform: demo"}
    with (
        patch(
            "homeassistant.loader.Integration.async_get_platform",
            side_effect=[None, ImportError("blablabla")],
        ),
        patch("homeassistant.loader.Integration.platforms_exists", return_value=True),
        patch("os.path.isfile", return_value=True),
        patch_yaml_files(files),
    ):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.keys() == {"homeassistant", "light"}
        warning = CheckConfigError(
            "Platform error 'light' from integration 'demo' - blablabla",
            None,
            None,
        )
        _assert_warnings_errors(res, [warning], [])


async def test_package_invalid(hass: HomeAssistant) -> None:
    """Test a platform setup with an invalid package config."""
    files = {YAML_CONFIG_FILE: BASE_CONFIG + '  packages:\n    p1:\n      group: ["a"]'}
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.keys() == {"homeassistant"}

        warning = CheckConfigError(
            (
                "Setup of package 'p1' failed: integration 'group' cannot be merged"
                ", expected a dict"
            ),
            "homeassistant.packages.p1.group",
            {"group": ["a"]},
        )
        _assert_warnings_errors(res, [warning], [])


async def test_package_definition_invalid_slug_keys(hass: HomeAssistant) -> None:
    """Test a platform setup with a broken package: keys must be slugs."""
    files = {
        YAML_CONFIG_FILE: BASE_CONFIG
        + '  packages:\n    not a slug:\n      group: ["a"]'
    }
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.keys() == {"homeassistant"}

        warning = CheckConfigError(
            (
                "Setup of package 'not a slug' failed: Invalid package definition 'not a slug': invalid slug not a "
                "slug (try not_a_slug). Package will not be initialized"
            ),
            "homeassistant.packages.not a slug",
            {"group": ["a"]},
        )
        _assert_warnings_errors(res, [warning], [])


async def test_package_definition_invalid_dict(hass: HomeAssistant) -> None:
    """Test a platform setup with a broken package: packages must be dicts."""
    files = {
        YAML_CONFIG_FILE: BASE_CONFIG
        + '  packages:\n    not_a_dict:\n      - group: ["a"]'
    }
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.keys() == {"homeassistant"}

        warning = CheckConfigError(
            (
                "Setup of package 'not_a_dict' failed: Invalid package definition 'not_a_dict': expected a "
                "dictionary. Package will not be initialized"
            ),
            "homeassistant.packages.not_a_dict",
            [{"group": ["a"]}],
        )
        _assert_warnings_errors(res, [warning], [])


async def test_package_schema_invalid(hass: HomeAssistant) -> None:
    """Test an invalid platform config because of severely broken packages section."""
    files = {
        YAML_CONFIG_FILE: "homeassistant:\n  packages:\n    - must\n    - not\n    - be\n    - a\n    - list"
    }
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        error = CheckConfigError(
            (
                f"Invalid config for 'homeassistant' at {YAML_CONFIG_FILE}, line 2:"
                " expected a dictionary for dictionary value 'packages', got ['must', 'not', 'be', 'a', 'list']"
            ),
            "homeassistant",
            {"packages": ["must", "not", "be", "a", "list"]},
        )
        _assert_warnings_errors(res, [], [error])


async def test_missing_included_file(hass: HomeAssistant) -> None:
    """Test missing included file."""
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "automation: !include no.yaml"}
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert len(res.errors) == 1
        assert len(res.warnings) == 0

        assert res.errors[0].message.startswith("Error loading")
        assert res.errors[0].domain is None
        assert res.errors[0].config is None


async def test_automation_config_platform(hass: HomeAssistant) -> None:
    """Test automation async config."""
    files = {
        YAML_CONFIG_FILE: BASE_CONFIG
        + """
automation:
  use_blueprint:
    path: test_event_service.yaml
    input:
      trigger_event: blueprint_event
      service_to_call: test.automation
input_datetime:
""",
        hass.config.path("blueprints/automation/test_event_service.yaml"): """
blueprint:
  name: "Call service based on event"
  domain: automation
  input:
    trigger_event:
    service_to_call:
trigger:
  platform: event
  event_type: !input trigger_event
action:
  service: !input service_to_call
""",
    }
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        assert len(res.get("automation", [])) == 1
        assert len(res.errors) == 0
        assert len(res.warnings) == 0
        assert "input_datetime" in res


@pytest.mark.parametrize(
    ("exception", "errors", "warnings", "message"),
    [
        (
            Exception("Broken"),
            1,
            0,
            "Unexpected error calling config validator: Broken",
        ),
        (
            HomeAssistantError("Broken"),
            0,
            1,
            "Invalid config for 'bla' at configuration.yaml, line 11: Broken",
        ),
    ],
)
async def test_config_platform_raise(
    hass: HomeAssistant,
    exception: Exception,
    errors: int,
    warnings: int,
    message: str,
) -> None:
    """Test bad config validation platform."""
    mock_platform(
        hass,
        "bla.config",
        Mock(async_validate_config=Mock(side_effect=exception)),
    )
    files = {
        YAML_CONFIG_FILE: BASE_CONFIG
        + """
bla:
  value: 1
""",
    }
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        error = CheckConfigError(
            message,
            "bla",
            {"value": 1},
        )
        _assert_warnings_errors(res, [error] * warnings, [error] * errors)


async def test_removed_yaml_support(hass: HomeAssistant) -> None:
    """Test config validation check with removed CONFIG_SCHEMA without raise if present."""
    mock_integration(
        hass,
        MockModule(
            domain="bla", config_schema=cv.removed("bla", raise_if_present=False)
        ),
        False,
    )
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "bla:\n  platform: demo"}
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.keys() == {"homeassistant"}
        _assert_warnings_errors(res, [], [])
