"""Test check_config helper."""
import logging
from unittest.mock import Mock, patch

from homeassistant.config import YAML_CONFIG_FILE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.check_config import (
    CheckConfigError,
    async_check_ha_config_file,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.requirements import RequirementsNotFound

from tests.common import MockModule, mock_integration, mock_platform, patch_yaml_files

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
    cnt = 0
    _LOGGER.debug("CONFIG - %s lines - %s errors", len(conf), len(conf.errors))
    for key, val in conf.items():
        _LOGGER.debug("#%s - %s: %s", cnt, key, val)
        cnt += 1
    for cnt, err in enumerate(conf.errors):
        _LOGGER.debug("error[%s] = %s", cnt, err)


async def test_bad_core_config(hass: HomeAssistant) -> None:
    """Test a bad core config setup."""
    files = {YAML_CONFIG_FILE: BAD_CORE_CONFIG}
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert isinstance(res.errors[0].message, str)
        assert res.errors[0].domain == "homeassistant"
        assert res.errors[0].config == {"unit_system": "bad"}

        # Only 1 error expected
        res.errors.pop(0)
        assert not res.errors


async def test_config_platform_valid(hass: HomeAssistant) -> None:
    """Test a valid platform setup."""
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "light:\n  platform: demo"}
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.keys() == {"homeassistant", "light"}
        assert res["light"] == [{"platform": "demo"}]
        assert not res.errors


async def test_component_platform_not_found(hass: HomeAssistant) -> None:
    """Test errors if component or platform not found."""
    # Make sure they don't exist
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "beer:"}
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.keys() == {"homeassistant"}
        assert res.errors[0] == CheckConfigError(
            "Integration error: beer - Integration 'beer' not found.", None, None
        )

        # Only 1 error expected
        res.errors.pop(0)
        assert not res.errors


async def test_component_requirement_not_found(hass: HomeAssistant) -> None:
    """Test errors if component with a requirement not found not found."""
    # Make sure they don't exist
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "test_custom_component:"}
    with patch(
        "homeassistant.helpers.check_config.async_get_integration_with_requirements",
        side_effect=RequirementsNotFound("test_custom_component", ["any"]),
    ), patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.keys() == {"homeassistant"}
        assert res.errors[0] == CheckConfigError(
            (
                "Integration error: test_custom_component - Requirements for"
                " test_custom_component not found: ['any']."
            ),
            None,
            None,
        )

        # Only 1 error expected
        res.errors.pop(0)
        assert not res.errors


async def test_component_not_found_safe_mode(hass: HomeAssistant) -> None:
    """Test no errors if component not found in safe mode."""
    # Make sure they don't exist
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "beer:"}
    hass.config.safe_mode = True
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.keys() == {"homeassistant"}
        assert not res.errors


async def test_component_platform_not_found_2(hass: HomeAssistant) -> None:
    """Test errors if component or platform not found."""
    # Make sure they don't exist
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "light:\n  platform: beer"}
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.keys() == {"homeassistant", "light"}
        assert res["light"] == []

        assert res.errors[0] == CheckConfigError(
            "Platform error light.beer - Integration 'beer' not found.", None, None
        )

        # Only 1 error expected
        res.errors.pop(0)
        assert not res.errors


async def test_platform_not_found_safe_mode(hass: HomeAssistant) -> None:
    """Test no errors if platform not found in safe_mode."""
    # Make sure they don't exist
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "light:\n  platform: beer"}
    hass.config.safe_mode = True
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.keys() == {"homeassistant", "light"}
        assert res["light"] == []

        assert not res.errors


async def test_package_invalid(hass: HomeAssistant) -> None:
    """Test a valid platform setup."""
    files = {YAML_CONFIG_FILE: BASE_CONFIG + '  packages:\n    p1:\n      group: ["a"]'}
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.errors[0].domain == "homeassistant.packages.p1.group"
        assert res.errors[0].config == {"group": ["a"]}
        # Only 1 error expected
        res.errors.pop(0)
        assert not res.errors

        assert res.keys() == {"homeassistant"}


async def test_bootstrap_error(hass: HomeAssistant) -> None:
    """Test a valid platform setup."""
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "automation: !include no.yaml"}
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.errors[0].domain is None

        # Only 1 error expected
        res.errors.pop(0)
        assert not res.errors


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
        hass.config.path(
            "blueprints/automation/test_event_service.yaml"
        ): """
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
        assert "input_datetime" in res


async def test_config_platform_raise(hass: HomeAssistant) -> None:
    """Test bad config validation platform."""
    mock_platform(
        hass,
        "bla.config",
        Mock(async_validate_config=Mock(side_effect=Exception("Broken"))),
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
        assert len(res.errors) == 1
        err = res.errors[0]
        assert err.domain == "bla"
        assert err.message == "Unexpected error calling config validator: Broken"
        assert err.config == {"value": 1}


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
