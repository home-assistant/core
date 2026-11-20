"""Tests for explicit removal of gateways confirmed absent from ONECTA."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

from aiohttp import ClientError
from daikin_onecta import OnectaAuthenticationError, OnectaConnectionError, Site
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.daikin_onecta import async_remove_config_entry_device
from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.components.daikin_onecta.coordinator import (
    OnectaDataUpdateCoordinator,
    gateway_site_membership,
)
from homeassistant.components.daikin_onecta.entity import management_point_device_info
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import OAuth2TokenRequestError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import ChildDeviceInfo

from .conftest import MockOnectaClient
from .test_climate_snapshots import _async_setup_fixture, _load_gateway_devices


async def _async_fire_coordinator_update(
    hass: HomeAssistant,
    coordinator: OnectaDataUpdateCoordinator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Advance time until the next coordinator poll."""
    freezer.tick(coordinator.update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.fixture
async def missing_gateway(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> dr.DeviceEntry:
    """Retain a registered gateway absent from a successful cloud response."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    coordinator = config_entry.runtime_data
    gateway_id = next(iter(coordinator.data))
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, gateway_id), config_entry.entry_id
    )
    assert device_entry is not None
    mock_onecta_client.get_gateway_devices.return_value = []
    freezer.tick(coordinator.update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert coordinator.last_update_success
    assert not coordinator.data[gateway_id].present_in_cloud
    return device_entry


@pytest.mark.parametrize(
    ("linked_gateways", "expected"),
    [(None, False), (["other-gateway"], True)],
)
async def test_remove_missing_gateway_requires_complete_sites(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    missing_gateway: dr.DeviceEntry,
    linked_gateways: list[str] | None,
    expected: bool,
) -> None:
    """A complete Sites response is required before removing a missing gateway."""
    coordinator = config_entry.runtime_data
    coordinator.async_get_sites = AsyncMock(
        return_value=[Site(id="site", gateway_device_ids=linked_gateways)]
    )
    gateway_id = next(iter(coordinator.data))

    assert (
        await async_remove_config_entry_device(hass, config_entry, missing_gateway)
        is expected
    )
    assert gateway_id in coordinator.data
    assert not coordinator.data[gateway_id].present_in_cloud
    coordinator.async_get_sites.assert_awaited_once_with(use_cache=False)


@pytest.mark.parametrize(
    ("sites", "expected"),
    [
        ([], None),
        ([Site(id="site", gateway_device_ids=None)], None),
        ([Site(id="site", gateway_device_ids=["other-gateway"])], False),
        (
            [
                Site(id="unknown", gateway_device_ids=None),
                Site(id="linked", gateway_device_ids=["gateway"]),
            ],
            True,
        ),
    ],
)
def test_gateway_site_membership(sites: list[Site], expected: bool | None) -> None:
    """Membership is unknown for empty or incomplete site inventories."""
    assert gateway_site_membership(sites, "gateway") is expected


async def test_remove_missing_gateway_rejects_empty_sites(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    missing_gateway: dr.DeviceEntry,
) -> None:
    """An empty Sites response is not proof that a gateway was removed."""
    coordinator = config_entry.runtime_data
    coordinator.async_get_sites = AsyncMock(return_value=[])

    assert not await async_remove_config_entry_device(
        hass, config_entry, missing_gateway
    )
    assert coordinator.data
    coordinator.async_get_sites.assert_awaited_once_with(use_cache=False)


async def test_remove_gateway_absent_from_cached_devices(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    missing_gateway: dr.DeviceEntry,
) -> None:
    """Sites can confirm removal when the gateway is absent from cached data."""
    coordinator = config_entry.runtime_data
    gateway_id = next(
        identifier
        for domain, identifier in missing_gateway.identifiers
        if domain == DOMAIN
    )
    coordinator.data.pop(gateway_id)
    coordinator.async_get_sites = AsyncMock(
        return_value=[Site(id="site", gateway_device_ids=[])]
    )

    assert await async_remove_config_entry_device(hass, config_entry, missing_gateway)
    coordinator.async_get_sites.assert_awaited_once_with(use_cache=False)


async def test_remove_missing_gateway_rejects_site_membership(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    missing_gateway: dr.DeviceEntry,
) -> None:
    """A gateway linked to a site is not confirmed removed."""
    coordinator = config_entry.runtime_data
    coordinator.async_get_sites = AsyncMock(
        return_value=[Site(id="site", gateway_device_ids=list(coordinator.data))]
    )

    assert not await async_remove_config_entry_device(
        hass, config_entry, missing_gateway
    )


@pytest.mark.parametrize(
    "error",
    [
        OnectaConnectionError("failed", method="GET", path="/v1/sites"),
        ClientError("failed"),
        TimeoutError(),
        OAuth2TokenRequestError(
            domain=DOMAIN,
            request_info=AsyncMock(),
            status=401,
            message="token refresh failed",
        ),
    ],
)
async def test_remove_missing_gateway_rejects_failed_sites_lookup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    missing_gateway: dr.DeviceEntry,
    error: Exception,
) -> None:
    """A failed lookup must never be interpreted as an empty inventory."""
    coordinator = config_entry.runtime_data
    coordinator.async_get_sites = AsyncMock(side_effect=error)

    assert not await async_remove_config_entry_device(
        hass, config_entry, missing_gateway
    )
    assert coordinator.data


async def test_remove_missing_gateway_starts_reauth_for_sites_401(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    missing_gateway: dr.DeviceEntry,
) -> None:
    """Start reauthentication when the Sites endpoint rejects the access token."""
    coordinator = config_entry.runtime_data
    coordinator.async_get_sites = AsyncMock(
        side_effect=OnectaAuthenticationError(
            status=401,
            method="GET",
            path="/v1/sites",
        )
    )

    assert not await async_remove_config_entry_device(
        hass, config_entry, missing_gateway
    )
    assert len(hass.config_entries.flow.async_progress()) == 1


@pytest.mark.parametrize("online", [False, True])
async def test_remove_present_gateway_is_rejected_without_cloud_call(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    online: bool,
) -> None:
    """Being offline does not mean a gateway has been removed from the account."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    coordinator = config_entry.runtime_data
    gateway_id = next(iter(coordinator.data))
    coordinator.data[gateway_id].device.cloud_connection.value = online
    coordinator.async_get_sites = AsyncMock()
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, gateway_id), config_entry.entry_id
    )
    assert device_entry is not None

    assert not await async_remove_config_entry_device(hass, config_entry, device_entry)
    coordinator.async_get_sites.assert_not_awaited()


@pytest.mark.usefixtures("missing_gateway")
async def test_remove_account_device_is_rejected(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """The account device is removed only with its config entry."""
    config_entry.runtime_data.async_get_sites = AsyncMock()
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"account_{config_entry.unique_id}"), config_entry.entry_id
    )
    assert device_entry is not None

    assert not await async_remove_config_entry_device(hass, config_entry, device_entry)
    config_entry.runtime_data.async_get_sites.assert_not_awaited()


async def test_remove_management_point_device_is_rejected(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Sites inventory can confirm gateways only, not their child devices."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    coordinator = config_entry.runtime_data
    coordinator.async_get_sites = AsyncMock(return_value=[])
    gateway_id = next(iter(coordinator.data))
    management_point = next(
        point
        for point in coordinator.data[gateway_id].device.management_points
        if point.management_point_type not in {"gateway", "climateControl"}
    )
    device_entry = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"{gateway_id}_{management_point.embedded_id}"),
        config_entry.entry_id,
    )
    assert device_entry is not None

    assert not await async_remove_config_entry_device(hass, config_entry, device_entry)
    coordinator.async_get_sites.assert_not_awaited()


async def test_remove_empty_child_with_live_management_point(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Allow removing an empty child after its entities move to the gateway."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    gateway_id, device = next(iter(config_entry.runtime_data.data.items()))
    point = next(
        point
        for point in device.device.management_points
        if point.management_point_type == "climateControl"
    )
    gateway = device_registry.async_get_device_by_identifier(
        (DOMAIN, gateway_id), config_entry.entry_id
    )
    assert gateway is not None
    child = device_registry.async_get_or_create_child(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, f"{gateway_id}_{point.embedded_id}")},
        parent_device_id=gateway.id,
    )
    assert not er.async_entries_for_device(entity_registry, child.id)

    assert await async_remove_config_entry_device(hass, config_entry, child)


async def test_remove_missing_gateway_rejects_failed_poll(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    missing_gateway: dr.DeviceEntry,
) -> None:
    """Do not use cached absence after a failed poll."""
    coordinator = config_entry.runtime_data
    coordinator.last_update_success = False
    coordinator.async_get_sites = AsyncMock()

    assert not await async_remove_config_entry_device(
        hass, config_entry, missing_gateway
    )
    coordinator.async_get_sites.assert_not_awaited()


async def test_remove_missing_gateway_rechecks_presence_after_lookup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    missing_gateway: dr.DeviceEntry,
) -> None:
    """A gateway restored while Sites is awaited must not be removed."""
    coordinator = config_entry.runtime_data
    device = next(iter(coordinator.data.values()))

    async def restore_gateway(*, use_cache: bool = False) -> list[Site]:
        assert not use_cache
        device.set_device_data(device.device)
        return []

    coordinator.async_get_sites = AsyncMock(side_effect=restore_gateway)

    assert not await async_remove_config_entry_device(
        hass, config_entry, missing_gateway
    )
    assert device.present_in_cloud


async def test_remove_child_of_missing_gateway_requires_sites_confirmation(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    missing_gateway: dr.DeviceEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Do not remove a child until Sites confirms its missing parent is gone."""
    coordinator = config_entry.runtime_data
    gateway_id = next(
        identifier
        for domain, identifier in missing_gateway.identifiers
        if domain == DOMAIN
    )
    management_point = next(
        point
        for point in coordinator.data[gateway_id].device.management_points
        if point.management_point_type not in {"gateway", "climateControl"}
    )
    child = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"{gateway_id}_{management_point.embedded_id}"),
        config_entry.entry_id,
    )
    assert child is not None
    coordinator.async_get_sites = AsyncMock(
        return_value=[Site(id="site", gateway_device_ids=[gateway_id])]
    )

    assert not await async_remove_config_entry_device(hass, config_entry, child)
    coordinator.async_get_sites.assert_awaited_once_with(use_cache=False)


async def test_remove_child_of_missing_gateway_keeps_gateway_in_coordinator(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    missing_gateway: dr.DeviceEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Keep the unavailable gateway wrapper so its entities can recover."""
    coordinator = config_entry.runtime_data
    gateway_id = next(
        identifier
        for domain, identifier in missing_gateway.identifiers
        if domain == DOMAIN
    )
    management_point = next(
        point
        for point in coordinator.data[gateway_id].device.management_points
        if point.management_point_type not in {"gateway", "climateControl"}
    )
    child = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"{gateway_id}_{management_point.embedded_id}"),
        config_entry.entry_id,
    )
    assert child is not None
    coordinator.async_get_sites = AsyncMock(
        return_value=[Site(id="site", gateway_device_ids=[])]
    )

    assert await async_remove_config_entry_device(hass, config_entry, child)
    assert coordinator.data[gateway_id] is not None
    assert not coordinator.data[gateway_id].present_in_cloud


async def test_entities_recover_when_removed_gateway_returns_after_child_removal(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    missing_gateway: dr.DeviceEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Existing entities follow the retained gateway wrapper after it returns."""
    coordinator = config_entry.runtime_data
    gateway_id = next(
        identifier
        for domain, identifier in missing_gateway.identifiers
        if domain == DOMAIN
    )
    gateway_device = coordinator.data[gateway_id]
    point = next(
        point
        for point in gateway_device.device.management_points
        if point.management_point_type == "domesticHotWaterTank"
    )
    child = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"{gateway_id}_{point.embedded_id}"), config_entry.entry_id
    )
    assert child is not None
    coordinator.async_get_sites = AsyncMock(
        return_value=[Site(id="site", gateway_device_ids=[])]
    )

    assert await async_remove_config_entry_device(hass, config_entry, child)
    assert coordinator.data[gateway_id] is gateway_device
    climate_state = hass.states.get("climate.altherma_room_temperature")
    sensor_state = hass.states.get("sensor.altherma_control_mode")
    assert climate_state is not None and climate_state.state == "unavailable"
    assert sensor_state is not None and sensor_state.state == "unavailable"

    mock_onecta_client.get_gateway_devices.return_value = _load_gateway_devices(
        "minimal_data"
    )
    await _async_fire_coordinator_update(hass, coordinator, freezer)

    assert coordinator.data[gateway_id] is gateway_device
    climate_state = hass.states.get("climate.altherma_room_temperature")
    sensor_state = hass.states.get("sensor.altherma_control_mode")
    assert climate_state is not None and climate_state.state != "unavailable"
    assert sensor_state is not None and sensor_state.state != "unavailable"


async def test_removed_gateway_reappearing_does_not_reload_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    missing_gateway: dr.DeviceEntry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Existing dynamic entities recover when a removed gateway returns."""
    coordinator = config_entry.runtime_data
    gateway_id = next(
        identifier
        for domain, identifier in missing_gateway.identifiers
        if domain == DOMAIN
    )
    original_device = coordinator.data[gateway_id]
    coordinator.async_get_sites = AsyncMock(
        return_value=[Site(id="site", gateway_device_ids=["other-gateway"])]
    )
    assert await async_remove_config_entry_device(hass, config_entry, missing_gateway)
    assert coordinator.data[gateway_id] is original_device
    assert not original_device.present_in_cloud

    mock_onecta_client.get_gateway_devices.return_value = _load_gateway_devices(
        "minimal_data"
    )
    with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
        await _async_fire_coordinator_update(hass, coordinator, freezer)

    assert coordinator.data[gateway_id].present_in_cloud
    assert coordinator.data[gateway_id] is original_device
    assert config_entry.runtime_data is coordinator
    climate_state = hass.states.get("climate.altherma_room_temperature")
    sensor_state = hass.states.get("sensor.altherma_control_mode")
    assert climate_state is not None and climate_state.state != "unavailable"
    assert sensor_state is not None and sensor_state.state != "unavailable"
    schedule_reload.assert_not_called()


async def test_removed_gateway_is_registered_again_when_it_returns(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Re-register a gateway whose registry entry was removed while absent."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    coordinator = config_entry.runtime_data
    gateway_id, device = next(iter(coordinator.data.items()))
    point = next(
        point
        for point in device.device.management_points
        if point.management_point_type == "domesticHotWaterTank"
    )
    mock_onecta_client.get_gateway_devices.return_value = []
    await _async_fire_coordinator_update(hass, coordinator, freezer)

    gateway_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, gateway_id), config_entry.entry_id
    )
    assert gateway_entry is not None
    coordinator.async_get_sites = AsyncMock(
        return_value=[Site(id="site", gateway_device_ids=[])]
    )
    assert await async_remove_config_entry_device(hass, config_entry, gateway_entry)
    device_registry.async_remove_device(gateway_entry.id)
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, gateway_id), config_entry.entry_id
        )
        is None
    )

    mock_onecta_client.get_gateway_devices.return_value = _load_gateway_devices(
        "altherma"
    )
    await _async_fire_coordinator_update(hass, coordinator, freezer)

    restored_gateway = device_registry.async_get_device_by_identifier(
        (DOMAIN, gateway_id), config_entry.entry_id
    )
    assert restored_gateway is not None
    assert device.ha_device_id == restored_gateway.id
    child_info = management_point_device_info(device, point.embedded_id)
    assert isinstance(child_info, ChildDeviceInfo)
    restored_child = device_registry.async_get_or_create_child_from_info(
        config_entry_id=config_entry.entry_id,
        device_info=child_info,
    )
    assert restored_child.parent_device_id == restored_gateway.id


async def test_disabled_sensor_is_recreated_after_gateway_removal(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    missing_gateway: dr.DeviceEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Recreate a disabled-by-default sensor after its gateway is removed."""
    coordinator = config_entry.runtime_data
    sensor_entity_id = "sensor.altherma_ip_address"
    disabled_sensor = entity_registry.async_get(sensor_entity_id)
    assert disabled_sensor is not None and disabled_sensor.disabled
    coordinator.async_get_sites = AsyncMock(
        return_value=[Site(id="site", gateway_device_ids=[])]
    )

    assert await async_remove_config_entry_device(hass, config_entry, missing_gateway)
    device_registry.async_remove_device(missing_gateway.id)
    assert entity_registry.async_get(sensor_entity_id) is None

    mock_onecta_client.get_gateway_devices.return_value = _load_gateway_devices(
        "minimal_data"
    )
    await _async_fire_coordinator_update(hass, coordinator, freezer)

    restored_sensor = entity_registry.async_get(sensor_entity_id)
    assert restored_sensor is not None and restored_sensor.disabled


async def test_removed_child_reappearing_does_not_reload_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Existing child entities recover when a removed point returns."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    coordinator = config_entry.runtime_data
    original_devices = _load_gateway_devices("minimal_data")
    gateway_id = original_devices[0].id
    management_point = next(
        point
        for point in original_devices[0].management_points
        if point.management_point_type == "domesticHotWaterTank"
    )
    embedded_id = management_point.embedded_id
    child = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"{gateway_id}_{embedded_id}"), config_entry.entry_id
    )
    assert child is not None

    missing_point_devices = deepcopy(original_devices)
    missing_point_devices[0].management_points = [
        point
        for point in missing_point_devices[0].management_points
        if point.embedded_id != embedded_id
    ]
    mock_onecta_client.get_gateway_devices.return_value = missing_point_devices
    await _async_fire_coordinator_update(hass, coordinator, freezer)
    assert coordinator.data[gateway_id].present_in_cloud
    assert coordinator.data[gateway_id].management_point(embedded_id) is None

    assert await async_remove_config_entry_device(hass, config_entry, child)

    mock_onecta_client.get_gateway_devices.return_value = original_devices
    with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
        await _async_fire_coordinator_update(hass, coordinator, freezer)

    assert coordinator.data[gateway_id].management_point(embedded_id) is not None
    assert config_entry.runtime_data is coordinator
    schedule_reload.assert_not_called()


async def test_remove_gateway_when_unloaded_is_rejected(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """No cloud inventory is known before the integration is loaded."""
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, "gateway")}
    )

    assert not await async_remove_config_entry_device(hass, config_entry, device_entry)
