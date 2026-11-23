"""Test Daikin Onecta setup."""

from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from daikin_onecta import Site
from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import FAKE_ACCESS_TOKEN, MockOnectaClient
from .platform_helpers import _async_setup_fixture, _load_gateway_devices

GATEWAY_DEVICES_URL = "https://api.onecta.daikineurope.com/v1/gateway-devices"
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "issue_841_gateway_devices.json"
_ALTHERMA_DOMESTIC_HOT_WATER_CHILD_IDENTIFIER = (
    DOMAIN,
    "00000000-0000-4000-8000-000000000105_domesticHotWaterTank",
)


async def test_unload_config_entry_cancels_post_write_refresh(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Cancel a pending post-write refresh when unloading the entry."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    coordinator = config_entry.runtime_data
    coordinator.schedule_post_write_refresh()
    mock_onecta_client.get_gateway_devices.reset_mock()

    assert config_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_onecta_client.get_gateway_devices.assert_not_awaited()


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
    """Return the registered domestic-hot-water management-point device."""
    identifier = _ALTHERMA_DOMESTIC_HOT_WATER_CHILD_IDENTIFIER
    child = device_registry.async_get_device_by_identifier(
        identifier, config_entry.entry_id
    ) or device_registry.async_get_child_device_by_identifier(
        identifier, config_entry.entry_id
    )
    assert child is not None
    return child


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
    config_entry.runtime_data.async_get_sites = AsyncMock(
        return_value=[Site(id="site", gateway_device_ids=["other-gateway"])]
    )

    response = await _async_remove_device(hass, hass_ws_client, child)

    assert response["success"]
    assert device_registry.async_get(child.id) is None


async def test_remove_management_point_device_management_point_gone(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Remove a child whose point and all enabled entities disappeared."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    child = _get_domestic_hot_water_tank_child(config_entry, device_registry)
    child_entities = er.async_entries_for_device(entity_registry, child.id)
    assert child_entities
    for entity_entry in child_entities:
        entity_registry.async_update_entity(
            entity_entry.entity_id,
            disabled_by=er.RegistryEntryDisabler.USER,
        )
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


async def test_removed_management_point_entities_are_added_again(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Re-add entities after a removed management point returns to the cloud."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    coordinator = config_entry.runtime_data
    gateway_id, device = next(iter(coordinator.data.items()))
    point = next(
        point
        for point in device.device.management_points
        if point.management_point_type == "domesticHotWaterTank"
    )
    embedded_id = point.embedded_id
    child = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{gateway_id}_{embedded_id}"), config_entry.entry_id
    ) or device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"{gateway_id}_{embedded_id}"), config_entry.entry_id
    )
    assert child is not None
    entity_unique_ids = {
        entry.unique_id
        for entry in er.async_entries_for_device(entity_registry, child.id)
    }
    assert entity_unique_ids

    original_devices = _load_gateway_devices("altherma")
    missing_devices = deepcopy(original_devices)
    missing_devices[0].management_points = [
        management_point
        for management_point in missing_devices[0].management_points
        if management_point.embedded_id != embedded_id
    ]
    mock_onecta_client.get_gateway_devices.return_value = missing_devices
    await _async_poll(hass, config_entry, freezer)

    response = await _async_remove_device(hass, hass_ws_client, child)
    assert response["success"]
    assert not er.async_entries_for_device(entity_registry, child.id)

    mock_onecta_client.get_gateway_devices.return_value = original_devices
    await _async_poll(hass, config_entry, freezer)

    new_unique_ids = {
        entry.unique_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
    }
    assert entity_unique_ids <= new_unique_ids


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
