"""Mocks for powerwall."""

import json
import os

from asynctest import MagicMock, PropertyMock

from homeassistant.components.powerwall.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS

from tests.common import load_fixture


async def _mock_powerwall_with_fixtures(hass):
    """Mock data used to build powerwall state."""
    meters = await _async_load_json_fixture(hass, "meters.json")
    sitemaster = await _async_load_json_fixture(hass, "sitemaster.json")
    site_info = await _async_load_json_fixture(hass, "site_info.json")
    return _mock_powerwall_return_value(
        site_info=site_info,
        charge=47.31993232,
        sitemaster=sitemaster,
        meters=meters,
        grid_status="SystemGridConnected",
    )


def _mock_powerwall_return_value(
    site_info=None, charge=None, sitemaster=None, meters=None, grid_status=None
):
    powerwall_mock = MagicMock()
    type(powerwall_mock).site_info = PropertyMock(return_value=site_info)
    type(powerwall_mock).charge = PropertyMock(return_value=charge)
    type(powerwall_mock).sitemaster = PropertyMock(return_value=sitemaster)
    type(powerwall_mock).meters = PropertyMock(return_value=meters)
    type(powerwall_mock).grid_status = PropertyMock(return_value=grid_status)

    return powerwall_mock


def _mock_powerwall_side_effect(site_info=None):
    powerwall_mock = MagicMock()
    type(powerwall_mock).site_info = PropertyMock(side_effect=site_info)
    return powerwall_mock


async def _async_load_json_fixture(hass, path):
    fixture = await hass.async_add_executor_job(
        load_fixture, os.path.join("powerwall", path)
    )
    return json.loads(fixture)


def _mock_get_config():
    """Return a default powerwall config."""
    return {DOMAIN: {CONF_IP_ADDRESS: "1.2.3.4"}}
