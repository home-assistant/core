"""Test Daikin Onecta setup."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import FAKE_ACCESS_TOKEN, MockOnectaClient
from .test_climate_snapshots import _async_setup_fixture, _load_gateway_devices

GATEWAY_DEVICES_URL = "https://api.onecta.daikineurope.com/v1/gateway-devices"
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "issue_841_gateway_devices.json"


async def test_setup_with_gateway_missing_management_points(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Set up successfully when Daikin omits a gateway's management points."""
    gateway_devices = json.loads(FIXTURE_PATH.read_text())
    aioclient_mock.get(GATEWAY_DEVICES_URL, json=gateway_devices)

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow."
            "async_get_config_entry_implementation",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.daikin_onecta.coordinator."
            "OnectaDataUpdateCoordinator.async_get_access_token",
            new=AsyncMock(return_value=FAKE_ACCESS_TOKEN),
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    assert len(config_entry.runtime_data.data) == 1
    device = config_entry.runtime_data.data["test-altherma-gateway"]
    assert device.available
    assert device.device.management_points == []


def _get_domestic_hot_water_tank_child(
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> dr.AnyDeviceEntry:
    """Return the registered domestic-hot-water child device."""
    for device in config_entry.runtime_data.data.values():
        for point in device.device.management_points:
            if point.management_point_type != "domesticHotWaterTank":
                continue
            child = device_registry.async_get_child_device_by_identifier(
                (DOMAIN, f"{device.id}_{point.embedded_id}"), config_entry.entry_id
            )
            if child is not None:
                return child
    raise AssertionError("Domestic hot water child device was not registered")


async def _async_poll(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Run the next scheduled coordinator poll."""
    assert config_entry.runtime_data.update_interval is not None
    freezer.tick(config_entry.runtime_data.update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _async_remove_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device: dr.DeviceEntry,
) -> dict[str, Any]:
    """Remove a registry device through Home Assistant's websocket API."""
    assert await async_setup_component(hass, "config", {})
    client = await hass_ws_client(hass)
    return await client.remove_device(device.id)


async def test_remove_management_point_device_still_present(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Prevent removing a child whose management point is still in the cloud."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    child = _get_domestic_hot_water_tank_child(config_entry, device_registry)

    response = await _async_remove_device(hass, hass_ws_client, child)

    assert not response["success"]
    assert device_registry.async_get(child.id) is not None


async def test_remove_management_point_device_gateway_gone(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Allow removing a child after its gateway disappears from the cloud."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    child = _get_domestic_hot_water_tank_child(config_entry, device_registry)
    mock_onecta_client.get_gateway_devices.return_value = []
    await _async_poll(hass, config_entry, freezer)

    response = await _async_remove_device(hass, hass_ws_client, child)

    assert response["success"]
    assert device_registry.async_get(child.id) is None


async def test_remove_management_point_device_management_point_gone(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Allow removing a child whose point disappeared while its gateway remains."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    child = _get_domestic_hot_water_tank_child(config_entry, device_registry)
    updated_devices = _load_gateway_devices("altherma")
    updated_devices[0].management_points = [
        point
        for point in updated_devices[0].management_points
        if point.management_point_type != "domesticHotWaterTank"
    ]
    mock_onecta_client.get_gateway_devices.return_value = updated_devices
    await _async_poll(hass, config_entry, freezer)

    response = await _async_remove_device(hass, hass_ws_client, child)

    assert response["success"]
    assert device_registry.async_get(child.id) is None


async def test_remove_management_point_device_after_failed_poll(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Refuse child removal if the latest cloud poll failed."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    child = _get_domestic_hot_water_tank_child(config_entry, device_registry)
    assert await async_setup_component(hass, "config", {})
    client = await hass_ws_client(hass)
    device = next(iter(config_entry.runtime_data.data.values()))
    device.device.management_points = [
        point
        for point in device.device.management_points
        if point.management_point_type != "domesticHotWaterTank"
    ]
    config_entry.runtime_data.last_update_success = False

    response = await client.remove_device(child.id)

    assert not response["success"]
    assert device_registry.async_get(child.id) is not None
