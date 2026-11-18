"""Tests for explicit removal of gateways confirmed absent from ONECTA."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

from aiohttp import ClientError
from daikin_onecta import OnectaConnectionError, Site
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.daikin_onecta import async_remove_config_entry_device
from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.components.daikin_onecta.coordinator import (
    OnectaDataUpdateCoordinator,
    gateway_site_membership,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import OAuth2TokenRequestError
from homeassistant.helpers import device_registry as dr, entity_registry as er

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
    assert (gateway_id in coordinator.data) is not expected
    coordinator.async_get_sites.assert_awaited_once_with()


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
    coordinator.async_get_sites.assert_awaited_once_with()


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
    coordinator.async_get_sites.assert_awaited_once_with()


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


async def test_remove_account_device_is_rejected(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    missing_gateway: dr.DeviceEntry,
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

    async def restore_gateway() -> list[Site]:
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
    coordinator.async_get_sites.assert_awaited_once_with()


async def test_remove_child_of_missing_gateway_drops_gateway_from_coordinator(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    missing_gateway: dr.DeviceEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Drop a gateway from cached data when Sites confirms its removal."""
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
    assert gateway_id not in coordinator.data


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
    coordinator.async_get_sites = AsyncMock(
        return_value=[Site(id="site", gateway_device_ids=["other-gateway"])]
    )
    assert await async_remove_config_entry_device(hass, config_entry, missing_gateway)

    mock_onecta_client.get_gateway_devices.return_value = _load_gateway_devices(
        "minimal_data"
    )
    with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
        await _async_fire_coordinator_update(hass, coordinator, freezer)

    assert coordinator.data[gateway_id].present_in_cloud
    assert config_entry.runtime_data is coordinator
    schedule_reload.assert_not_called()


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
