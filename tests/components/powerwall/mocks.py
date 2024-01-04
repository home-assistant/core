"""Mocks for powerwall."""

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock

from tesla_powerwall import (
    DeviceType,
    GridStatus,
    MetersAggregatesResponse,
    Powerwall,
    PowerwallStatusResponse,
    SiteInfoResponse,
    SiteMasterResponse,
)

from tests.common import load_fixture

MOCK_GATEWAY_DIN = "111-0----2-000000000FFA"


async def _mock_powerwall_with_fixtures(hass):
    """Mock data used to build powerwall state."""
    async with asyncio.TaskGroup() as tg:
        meters = tg.create_task(_async_load_json_fixture(hass, "meters.json"))
        sitemaster = tg.create_task(_async_load_json_fixture(hass, "sitemaster.json"))
        site_info = tg.create_task(_async_load_json_fixture(hass, "site_info.json"))
        status = tg.create_task(_async_load_json_fixture(hass, "status.json"))
        device_type = tg.create_task(_async_load_json_fixture(hass, "device_type.json"))

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
):
    async with Powerwall("1.2.3.4") as powerwall:
        powerwall_mock = MagicMock(powerwall)

        powerwall_mock.get_site_info = AsyncMock(return_value=site_info)
        powerwall_mock.get_charge = AsyncMock(return_value=charge)
        powerwall_mock.get_sitemaster = AsyncMock(return_value=sitemaster)
        powerwall_mock.get_meters = AsyncMock(return_value=meters)
        powerwall_mock.get_grid_status = AsyncMock(return_value=grid_status)
        powerwall_mock.get_status = AsyncMock(return_value=status)
        powerwall_mock.get_device_type = AsyncMock(return_value=device_type)
        powerwall_mock.get_serial_numbers = AsyncMock(return_value=serial_numbers)
        powerwall_mock.get_backup_reserve_percentage = AsyncMock(
            return_value=backup_reserve_percentage
        )
        powerwall_mock.is_grid_services_active = AsyncMock(
            return_value=grid_services_active
        )

        return powerwall_mock


async def _mock_powerwall_site_name(hass, site_name):
    async with Powerwall("1.2.3.4") as powerwall:
        powerwall_mock = MagicMock(powerwall)

        site_info_resp = SiteInfoResponse(
            await _async_load_json_fixture(hass, "site_info.json")
        )
        # Sets site_info_resp.site_name to return site_name
        site_info_resp.response["site_name"] = site_name
        powerwall_mock.get_site_info = AsyncMock(return_value=site_info_resp)
        powerwall_mock.get_gateway_din = AsyncMock(return_value=MOCK_GATEWAY_DIN)

        return powerwall_mock


async def _mock_powerwall_side_effect(site_info=None):
    async with Powerwall("1.2.3.4") as powerwall:
        powerwall_mock = MagicMock(powerwall)

        powerwall_mock.get_site_info = AsyncMock(side_effect=site_info)
        return powerwall_mock


async def _async_load_json_fixture(hass, path):
    fixture = await hass.async_add_executor_job(
        load_fixture, os.path.join("powerwall", path)
    )
    return json.loads(fixture)
