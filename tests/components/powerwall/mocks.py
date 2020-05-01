"""Mocks for powerwall."""

import json
import os

from tesla_powerwall import (
    DeviceType,
    GridStatus,
    MetersAggregateResponse,
    Powerwall,
    PowerwallStatusResponse,
    SiteInfoResponse,
    SitemasterResponse,
)

from homeassistant.components.powerwall.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS

from tests.async_mock import MagicMock, Mock
from tests.common import load_fixture


async def _mock_powerwall_with_fixtures(hass):
    """Mock data used to build powerwall state."""
    meters = await _async_load_json_fixture(hass, "meters.json")
    sitemaster = await _async_load_json_fixture(hass, "sitemaster.json")
    site_info = await _async_load_json_fixture(hass, "site_info.json")
    status = await _async_load_json_fixture(hass, "status.json")
    device_type = await _async_load_json_fixture(hass, "device_type.json")

    return _mock_powerwall_return_value(
        site_info=SiteInfoResponse(site_info),
        charge=47,
        sitemaster=SitemasterResponse(sitemaster),
        meters=MetersAggregateResponse(meters),
        grid_status=GridStatus.CONNECTED,
        status=PowerwallStatusResponse(status),
        device_type=DeviceType(device_type["device_type"]),
        serial_numbers=["TG0123456789AB", "TG9876543210BA"],
    )


def _mock_powerwall_return_value(
    site_info=None,
    charge=None,
    sitemaster=None,
    meters=None,
    grid_status=None,
    status=None,
    device_type=None,
    serial_numbers=None,
):
    powerwall_mock = MagicMock(Powerwall("1.2.3.4"))
    powerwall_mock.get_site_info = Mock(return_value=site_info)
    powerwall_mock.get_charge = Mock(return_value=charge)
    powerwall_mock.get_sitemaster = Mock(return_value=sitemaster)
    powerwall_mock.get_meters = Mock(return_value=meters)
    powerwall_mock.get_grid_status = Mock(return_value=grid_status)
    powerwall_mock.get_status = Mock(return_value=status)
    powerwall_mock.get_device_type = Mock(return_value=device_type)
    powerwall_mock.get_serial_numbers = Mock(return_value=serial_numbers)

    return powerwall_mock


async def _mock_powerwall_site_name(hass, site_name):
    powerwall_mock = MagicMock(Powerwall("1.2.3.4"))

    site_info_resp = SiteInfoResponse(
        await _async_load_json_fixture(hass, "site_info.json")
    )
    site_info_resp.site_name = site_name
    powerwall_mock.get_site_info = Mock(return_value=site_info_resp)

    return powerwall_mock


def _mock_powerwall_side_effect(site_info=None):
    powerwall_mock = MagicMock(Powerwall("1.2.3.4"))
    powerwall_mock.get_site_info = Mock(side_effect=site_info)
    return powerwall_mock


async def _async_load_json_fixture(hass, path):
    fixture = await hass.async_add_executor_job(
        load_fixture, os.path.join("powerwall", path)
    )
    return json.loads(fixture)


def _mock_get_config():
    """Return a default powerwall config."""
    return {DOMAIN: {CONF_IP_ADDRESS: "1.2.3.4"}}
