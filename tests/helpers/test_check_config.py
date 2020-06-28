"""Test check_config helper."""
import logging

from homeassistant.config import YAML_CONFIG_FILE
from homeassistant.helpers.check_config import (
    CheckConfigError,
    async_check_ha_config_file,
)

from tests.async_mock import patch
from tests.common import patch_yaml_files

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


async def test_bad_core_config(hass, loop):
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


async def test_config_platform_valid(hass, loop):
    """Test a valid platform setup."""
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "light:\n  platform: demo"}
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.keys() == {"homeassistant", "light"}
        assert res["light"] == [{"platform": "demo"}]
        assert not res.errors


async def test_component_platform_not_found(hass, loop):
    """Test errors if component or platform not found."""
    # Make sure they don't exist
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "beer:"}
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.keys() == {"homeassistant"}
        assert res.errors[0] == CheckConfigError(
            "Component error: beer - Integration 'beer' not found.", None, None
        )

        # Only 1 error expected
        res.errors.pop(0)
        assert not res.errors


async def test_component_platform_not_found_2(hass, loop):
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


async def test_package_invalid(hass, loop):
    """Test a valid platform setup."""
    files = {
        YAML_CONFIG_FILE: BASE_CONFIG + ("  packages:\n    p1:\n" '      group: ["a"]')
    }
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.errors[0].domain == "homeassistant.packages.p1.group"
        assert res.errors[0].config == {"group": ["a"]}
        # Only 1 error expected
        res.errors.pop(0)
        assert not res.errors

        assert res.keys() == {"homeassistant"}


async def test_bootstrap_error(hass, loop):
    """Test a valid platform setup."""
    files = {YAML_CONFIG_FILE: BASE_CONFIG + "automation: !include no.yaml"}
    with patch("os.path.isfile", return_value=True), patch_yaml_files(files):
        res = await async_check_ha_config_file(hass)
        log_ha_config(res)

        assert res.errors[0].domain is None

        # Only 1 error expected
        res.errors.pop(0)
        assert not res.errors
