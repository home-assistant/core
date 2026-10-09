"""Tests for Daikin Onecta diagnostics."""

from unittest.mock import AsyncMock

from daikin_onecta import OnectaConnectionError, Site

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from .test_climate_snapshots import _async_setup_fixture

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test cached cloud data is provided with identifying data redacted."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    api = config_entry.runtime_data.api
    api.client.get_gateway_devices = AsyncMock()
    api.client.get_sites = AsyncMock(
        return_value=[
            Site(
                id="site-1",
                name="Home",
                gateway_device_ids=[
                    device.id
                    for device in (config_entry.runtime_data.data or {}).values()
                ],
            )
        ]
    )

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    assert diagnostics["config_entry"]["data"]["token"] == REDACTED
    assert diagnostics["devices"]
    assert diagnostics["devices"][0]["id"] == REDACTED
    gateway = next(
        point
        for point in diagnostics["devices"][0]["management_points"]
        if point["management_point_type"] == "gateway"
    )
    assert gateway["characteristics"]["ipAddress"] == REDACTED
    assert diagnostics["sites"]["data"][0]["id"] == REDACTED
    assert diagnostics["sites"]["data"][0]["name"] == REDACTED
    assert diagnostics["sites"]["gateway_membership"][0] == {
        "gateway_device_id": REDACTED,
        "linked_to_site": True,
    }
    api.client.get_sites.assert_awaited_once_with()
    api.client.get_gateway_devices.assert_not_awaited()


async def test_diagnostics_redacts_gateway_ssids(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Redact gateway Wi-Fi names from cached cloud data."""
    await _async_setup_fixture(hass, config_entry, "climate_floorheatingairflow")
    api = config_entry.runtime_data.api
    api.client.get_gateway_devices = AsyncMock()
    api.client.get_sites = AsyncMock(return_value=[])

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    gateways = [
        point
        for device in diagnostics["devices"]
        for point in device["management_points"]
        if point["management_point_type"] == "gateway"
    ]
    assert gateways
    for gateway in gateways:
        characteristics = gateway["characteristics"]
        assert characteristics["ssid"] == REDACTED
        assert characteristics["wifiConnectionSSID"] == REDACTED


async def test_diagnostics_reports_site_lookup_failures(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Keep diagnostics available when the explicit Sites lookup fails."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    config_entry.runtime_data.api.client.get_sites = AsyncMock(
        side_effect=OnectaConnectionError(
            "network unavailable", method="GET", path="/v1/sites"
        )
    )

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    assert diagnostics["sites"]["error"] == {
        "type": "OnectaConnectionError",
        "status": None,
    }
