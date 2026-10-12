"""Tests for explicit removal of gateways confirmed absent from ONECTA."""

from unittest.mock import AsyncMock

from aiohttp import ClientError
from daikin_onecta import OnectaConnectionError, Site
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.daikin_onecta import async_remove_config_entry_device
from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .test_climate_snapshots import _async_setup_fixture

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
async def missing_gateway(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> dr.DeviceEntry:
    """Retain a registered gateway absent from a successful cloud response."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    coordinator = config_entry.runtime_data
    gateway_id = next(iter(coordinator.data))
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, gateway_id), config_entry.entry_id
    )
    assert device_entry is not None
    coordinator._async_get_cloud_devices = AsyncMock(return_value=[])
    freezer.tick(coordinator.update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert coordinator.last_update_success
    assert not coordinator.data[gateway_id].present_in_cloud
    return device_entry


@pytest.mark.parametrize(
    ("linked_gateways", "expected"),
    [(None, False), ([], True), (["other-gateway"], True)],
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
    device_entry = next(
        entry
        for entry in dr.async_entries_for_config_entry(
            device_registry, config_entry.entry_id
        )
        if any(
            domain == DOMAIN and identifier.startswith(f"{gateway_id}_")
            for domain, identifier in entry.identifiers
        )
    )

    assert not await async_remove_config_entry_device(hass, config_entry, device_entry)
    coordinator.async_get_sites.assert_not_awaited()


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
