"""Fixtures for adguard tests."""

from unittest.mock import patch

import pytest

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONTENT_TYPE_JSON

from .const import FIXTURE_USER_INPUT

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(name="bypass_version")
def bypass_version_fixture(aioclient_mock: AiohttpClientMocker):
    """Prevent version call."""
    aioclient_mock.get(
        f"{'https' if FIXTURE_USER_INPUT[CONF_SSL] else 'http'}"
        f"://{FIXTURE_USER_INPUT[CONF_HOST]}"
        f":{FIXTURE_USER_INPUT[CONF_PORT]}/control/status",
        json={"version": "v0.99.0"},
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )


@pytest.fixture(name="bypass_switch_state_update")
def bypass_switch_state_update_fixture():
    """Prevent switch state API calls."""
    with patch(
        "homeassistant.components.adguard.switch.AdGuardHomeProtectionSwitch._adguard_update"
    ), patch(
        "homeassistant.components.adguard.switch.AdGuardHomeParentalSwitch._adguard_update"
    ), patch(
        "homeassistant.components.adguard.switch.AdGuardHomeSafeSearchSwitch._adguard_update"
    ), patch(
        "homeassistant.components.adguard.switch.AdGuardHomeSafeBrowsingSwitch._adguard_update"
    ), patch(
        "homeassistant.components.adguard.switch.AdGuardHomeFilteringSwitch._adguard_update"
    ), patch(
        "homeassistant.components.adguard.switch.AdGuardHomeQueryLogSwitch._adguard_update"
    ):
        yield


@pytest.fixture(name="disable_sensors")
def disable_sensors_fixture():
    """Prevent sensor setup."""
    with patch("homeassistant.components.adguard.sensor.async_setup_entry"):
        yield
