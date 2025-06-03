"""Mocks for powerwall."""

import asyncio
import json
import os
from unittest.mock import MagicMock

from tesla_powerwall import (
    BatteryResponse,
    DeviceType,
    GridStatus,
    MetersAggregatesResponse,
    Powerwall,
    PowerwallStatusResponse,
    SiteInfoResponse,
    SiteMasterResponse,
)

from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonValueType

from tests.common import load_fixture

MOCK_GATEWAY_DIN = "111-0----2-000000000FFA"


async def _mock_powerwall_with_fixtures(
    hass: HomeAssistant, empty_meters: bool = False
) -> MagicMock:
    """Mock data used to build powerwall state."""
    async with asyncio.TaskGroup() as tg:
        meters_file = "meters_empty.json" if empty_meters else "meters.json"
        meters = tg.create_task(_async_load_json_fixture(hass, meters_file))
        sitemaster = tg.create_task(_async_load_json_fixture(hass, "sitemaster.json"))
        site_info = tg.create_task(_async_load_json_fixture(hass, "site_info.json"))
        status = tg.create_task(_async_load_json_fixture(hass, "status.json"))
        device_type = tg.create_task(_async_load_json_fixture(hass, "device_type.json"))
        batteries = tg.create_task(_async_load_json_fixture(hass, "batteries.json"))

    return await _mock_powerwall_return_value(
        site_info=SiteInfoResponse.from_dict(site_info.result()),
        charge=47.34587394586,
        sitemaster=SiteMasterResponse.from_dict(sitemaster.result()),
        meters=MetersAggregatesResponse.from_dict(meters.result()),
        grid_services_active=True,
        grid_status=GridStatus.CONNECTED,
        status=PowerwallStatusResponse.from_dict(status.result()),
        device_type=DeviceType(device_type.result()["device_type"]),
        serial_numbers=["TG0123456789AB", "TG9876543210BA"],
        backup_reserve_percentage=15.0,
        batteries=[
            BatteryResponse.from_dict(battery) for battery in batteries.result()
        ],
    )


async def _mock_powerwall_return_value(
    site_info=None,
    charge=None,
    sitemaster=None,
    meters=None,
    grid_services_active=None,
    grid_status=None,
    status=None,
    device_type=None,
    serial_numbers=None,
    backup_reserve_percentage=None,
    batteries=None,
):
    powerwall_mock = MagicMock(Powerwall)
    powerwall_mock.__aenter__.return_value = powerwall_mock

    powerwall_mock.get_site_info.return_value = site_info
    powerwall_mock.get_charge.return_value = charge
    powerwall_mock.get_sitemaster.return_value = sitemaster
    powerwall_mock.get_meters.return_value = meters
    powerwall_mock.get_grid_status.return_value = grid_status
    powerwall_mock.get_status.return_value = status
    powerwall_mock.get_device_type.return_value = device_type
    powerwall_mock.get_serial_numbers.return_value = serial_numbers
    powerwall_mock.get_backup_reserve_percentage.return_value = (
        backup_reserve_percentage
    )
    powerwall_mock.is_grid_services_active.return_value = grid_services_active
    powerwall_mock.get_gateway_din.return_value = MOCK_GATEWAY_DIN
    powerwall_mock.get_batteries.return_value = batteries

    return powerwall_mock


async def _mock_powerwall_site_name(hass: HomeAssistant, site_name: str) -> MagicMock:
    powerwall_mock = MagicMock(Powerwall)
    powerwall_mock.__aenter__.return_value = powerwall_mock

    site_info_resp = SiteInfoResponse.from_dict(
        await _async_load_json_fixture(hass, "site_info.json")
    )
    site_info_resp._raw["site_name"] = site_name
    site_info_resp.site_name = site_name
    powerwall_mock.get_site_info.return_value = site_info_resp
    powerwall_mock.get_gateway_din.return_value = MOCK_GATEWAY_DIN

    return powerwall_mock


async def _mock_powerwall_side_effect(site_info=None):
    powerwall_mock = MagicMock(Powerwall)
    powerwall_mock.__aenter__.return_value = powerwall_mock

    powerwall_mock.get_site_info.side_effect = site_info
    return powerwall_mock


async def _async_load_json_fixture(hass: HomeAssistant, path: str) -> JsonValueType:
    fixture = await hass.async_add_executor_job(
        load_fixture, os.path.join("powerwall", path)
    )
    return json.loads(fixture)
