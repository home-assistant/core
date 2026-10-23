"""Tests for TP-Link Omada integration init."""

import asyncio
from datetime import timedelta
from functools import partial
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
    async_load_json_object_fixture,
)
from tplink_omada_client.devices import OmadaGateway, OmadaListDevice
from tplink_omada_client.exceptions import (
    ConnectionFailed,
    LoginFailed,
    OmadaClientException,
    UnsupportedControllerVersion,
)

from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.components.tplink_omada.controller import OmadaSiteController
from homeassistant.components.tplink_omada.coordinator import (
    EMPTY_DEVICE_LIMIT,
    EMPTY_DEVICE_WINDOW,
    POLL_CLIENTS,
    POLL_UPGRADE,
    OmadaCoordinator,
    async_cleanup_devices,
    device_removal_is_confirmed,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

MOCK_ENTRY_DATA = {
    "host": "https://fake.omada.host",
    "verify_ssl": True,
    "site": "SiteId",
    "username": "test-username",
    "password": "test-password",
}


async def _async_poll_devices(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Advance to the next device poll and let it complete."""
    freezer.tick(timedelta(seconds=POLL_CLIENTS + 1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.parametrize(
    ("side_effect", "entry_state", "translation_key"),
    [
        (
            UnsupportedControllerVersion("4.0.0"),
            ConfigEntryState.SETUP_ERROR,
            "unsupported_controller",
        ),
        (
            LoginFailed(401, "invalid credentials"),
            ConfigEntryState.SETUP_ERROR,
            "auth_failed",
        ),
        (
            ConnectionFailed(),
            ConfigEntryState.SETUP_RETRY,
            "cannot_connect",
        ),
        (
            OmadaClientException(),
            ConfigEntryState.SETUP_RETRY,
            "unexpected_error",
        ),
    ],
)
async def test_setup_entry_login_failed_raises_configentryauthfailed(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: OmadaClientException,
    entry_state: ConfigEntryState,
    translation_key: str,
) -> None:
    """Test setup entry with login failed raises ConfigEntryAuthFailed."""
    mock_omada_client.login.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is entry_state
    assert mock_config_entry.error_reason_translation_key == translation_key
    assert mock_config_entry.error_reason_translation_placeholders is None


async def test_coordinator_update_failure_is_translated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_omada_site_client: MagicMock,
) -> None:
    """Test coordinator API failures raise a translated UpdateFailed."""
    coordinator = OmadaCoordinator(
        hass, mock_config_entry, mock_omada_site_client, "test"
    )
    with (
        patch.object(
            OmadaCoordinator,
            "poll_update",
            side_effect=OmadaClientException("boom"),
        ),
        pytest.raises(UpdateFailed) as err,
    ):
        await coordinator._async_update_data()

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "api_error"


async def test_automatic_missing_device_cleanup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_omada_client: MagicMock,
) -> None:
    """Test missing devices are removed during initial startup cleanup.

    This validates the cleanup mechanism scheduled immediately on entry setup,
    which runs as a background task.
    """
    mock_config_entry = MockConfigEntry(
        title="Test Omada Controller",
        domain=DOMAIN,
        data=dict(MOCK_ENTRY_DATA),
        unique_id="12345_SiteId",
        version=2,
    )
    mock_config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "99:99:99:99:99:99")},
        manufacturer="TPLink",
        name="Old Device",
        model="Some old model",
    )

    assert device_registry.async_get(device_entry.id) == device_entry

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert device_registry.async_get(device_entry.id) is None


async def test_cleanup_devices_removes_orphans(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test cleanup helper removes orphaned device registry entries."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    controller = hass.config_entries.async_get_entry(
        mock_config_entry.entry_id
    ).runtime_data

    orphan = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "99:99:99:99:99:99")},
        manufacturer="TP-Link",
        model="Test",
        name="Orphan",
    )
    assert device_registry.async_get(orphan.id)

    await async_cleanup_devices(hass, controller)

    assert device_registry.async_get(orphan.id) is None


async def test_cleanup_preserves_controller_device(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device cleanup keeps the controller device entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    controller = hass.config_entries.async_get_entry(
        mock_config_entry.entry_id
    ).runtime_data

    controller_mac = "00-11-22-33-44-55"
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, controller_mac), mock_config_entry.entry_id
    )

    await async_cleanup_devices(hass, controller)

    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, controller_mac), mock_config_entry.entry_id
    )


async def test_startup_cleanup_runs_before_platform_setup(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test stale entries release entity IDs before platforms are set up."""
    mock_config_entry.add_to_hass(hass)

    stale_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "99:99:99:99:99:99")},
        manufacturer="TP-Link",
        model="Test",
        name="Test PoE Switch",
    )
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "stale_device_status",
        config_entry=mock_config_entry,
        device_id=stale_device.id,
        suggested_object_id="test_poe_switch_device_status",
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert device_registry.async_get(stale_device.id) is None
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, "54-AF-97-00-00-01_device_status"
        )
        == "sensor.test_poe_switch_device_status"
    )


async def test_cleanup_task_guard_prevents_redundant_tasks(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test in-flight task guard prevents scheduling a second cleanup concurrently."""
    cleanup_call_count = 0
    cleanup_started = asyncio.Event()
    cleanup_proceed = asyncio.Event()

    async def blocking_cleanup(h: HomeAssistant, c: OmadaSiteController) -> None:
        nonlocal cleanup_call_count
        cleanup_call_count += 1
        if cleanup_call_count == 1:
            # The startup sweep runs during setup, before platforms are added
            return
        cleanup_started.set()
        await cleanup_proceed.wait()

    with patch(
        "homeassistant.components.tplink_omada.async_cleanup_devices",
        new=blocking_cleanup,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # The first scheduled run starts a cleanup background task
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=1, seconds=1))
        await hass.async_block_till_done()
        assert cleanup_started.is_set()

        # The in-flight guard makes the next interval a no-op
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=2, seconds=1))
        await hass.async_block_till_done()

        # Release the in-flight cleanup
        cleanup_proceed.set()
        await hass.async_block_till_done(wait_background_tasks=True)

    assert cleanup_call_count == 2


async def _get_devices_without(
    hass: HomeAssistant, excluded_mac: str
) -> list[OmadaListDevice]:
    """Return devices from the devices fixture, skipping one MAC."""
    devices_data = await async_load_json_array_fixture(hass, "devices.json", DOMAIN)
    return [
        OmadaListDevice(device)
        for device in devices_data
        if device["mac"] != excluded_mac
    ]


async def test_cleanup_runs_hourly(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a device removed from the controller is cleaned up hourly."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    removed_mac = "54-AF-97-00-00-01"
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, removed_mac), mock_config_entry.entry_id
    )

    site_client = mock_omada_client.get_site_client.return_value
    site_client.get_devices = AsyncMock(
        return_value=await _get_devices_without(hass, removed_mac)
    )

    # Fire the 1-hour interval to trigger cleanup
    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, removed_mac), mock_config_entry.entry_id
        )
        is None
    )


async def test_cleanup_recreates_device_when_reappears(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a device removed by cleanup is registered again when it returns."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    removed_mac = "54-AF-97-00-00-01"
    update_unique_id = f"{removed_mac}_firmware"
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, removed_mac), mock_config_entry.entry_id
    )
    assert (
        entity_registry.async_get_entity_id("update", DOMAIN, update_unique_id)
        is not None
    )

    site_client = mock_omada_client.get_site_client.return_value

    # Remove the switch from the controller's device list and clean up
    site_client.get_devices = AsyncMock(
        side_effect=partial(_get_devices_without, hass, removed_mac)
    )
    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, removed_mac), mock_config_entry.entry_id
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id("update", DOMAIN, update_unique_id) is None
    )

    # Switch returns to the controller, and the next run registers it again
    devices_data = await async_load_json_array_fixture(hass, "devices.json", DOMAIN)
    site_client.get_devices = AsyncMock(
        return_value=[OmadaListDevice(d) for d in devices_data]
    )
    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, removed_mac), mock_config_entry.entry_id
    )
    assert (
        entity_registry.async_get_entity_id("update", DOMAIN, update_unique_id)
        is not None
    )


async def test_cleanup_recreates_gateway_ports_after_successful_refresh(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a returning gateway is not rebuilt from stale port data."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    gateway_mac = "AA-BB-CC-DD-EE-FF"
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, gateway_mac), mock_config_entry.entry_id
    )

    def gateway_port_entities() -> list[er.RegistryEntry]:
        return [
            entry
            for entry in entity_registry.entities.values()
            if entry.platform == DOMAIN
            and entry.domain in {"binary_sensor", "switch"}
            and entry.unique_id.startswith(f"{gateway_mac}_")
        ]

    assert gateway_port_entities()

    site_client = mock_omada_client.get_site_client.return_value

    # Remove the gateway from the controller's device list and clean up.
    site_client.get_devices = AsyncMock(
        side_effect=partial(_get_devices_without, hass, gateway_mac)
    )
    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, gateway_mac), mock_config_entry.entry_id
        )
        is None
    )
    assert not gateway_port_entities()

    # The gateway returns, but its refresh fails: no port entities are built
    # from the cached port lists, and registration stays retryable.
    site_client.get_gateway = AsyncMock(
        side_effect=OmadaClientException("gateway unavailable")
    )
    devices_data = await async_load_json_array_fixture(hass, "devices.json", DOMAIN)
    site_client.get_devices = AsyncMock(
        return_value=[OmadaListDevice(device) for device in devices_data]
    )
    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not gateway_port_entities()

    # A successful refresh rebuilds the port entities.
    gateway_data = await async_load_json_object_fixture(
        hass, "gateway-TL-ER7212PC.json", DOMAIN
    )
    site_client.get_gateway = AsyncMock(return_value=OmadaGateway(gateway_data))
    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, gateway_mac), mock_config_entry.entry_id
    )
    assert gateway_port_entities()


async def test_cleanup_drops_switch_port_coordinator(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test removing a stale switch drops its cached port coordinator."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    controller = hass.config_entries.async_get_entry(
        mock_config_entry.entry_id
    ).runtime_data
    switch_mac = "54-AF-97-00-00-01"
    site_client = mock_omada_client.get_site_client.return_value

    devices_data = await async_load_json_array_fixture(hass, "devices.json", DOMAIN)
    switch_device = next(
        OmadaListDevice(device)
        for device in devices_data
        if device["mac"] == switch_mac
    )
    switch = await site_client.get_switch(switch_device)
    coordinator = controller.get_switch_port_coordinator(switch)
    assert controller.get_switch_port_coordinator(switch) is coordinator

    site_client.get_devices = AsyncMock(
        return_value=await _get_devices_without(hass, switch_mac)
    )
    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, switch_mac), mock_config_entry.entry_id
        )
        is None
    )
    assert controller.get_switch_port_coordinator(switch) is not coordinator


async def test_overlapping_registrations_register_device_once(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test overlapping device updates do not register a device twice."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    controller = hass.config_entries.async_get_entry(
        mock_config_entry.entry_id
    ).runtime_data
    switch_mac = "54-AF-97-00-00-01"
    site_client = mock_omada_client.get_site_client.return_value
    registration_started = asyncio.Event()
    registration_proceed = asyncio.Event()
    calls = 0

    async def _register(device: OmadaListDevice) -> None:
        """Register a device and hold the first call open."""
        nonlocal calls
        calls += 1
        if calls == 1:
            registration_started.set()
            await registration_proceed.wait()

    registration = asyncio.create_task(
        controller.async_register_device_entities(
            lambda device: dr.format_mac(device.mac) == dr.format_mac(switch_mac),
            _register,
        )
    )
    await registration_started.wait()

    # Another device-list update lands while the callback is still running
    devices_data = await async_load_json_array_fixture(hass, "devices.json", DOMAIN)
    site_client.get_devices = AsyncMock(
        return_value=[OmadaListDevice(d) for d in devices_data]
    )
    await _async_poll_devices(hass, freezer)

    registration_proceed.set()
    await registration
    await hass.async_block_till_done(wait_background_tasks=True)

    assert calls == 1


async def test_empty_device_limit_scales_with_fast_polling() -> None:
    """Test the empty-list window stays one hour when polling speeds up."""
    coordinator = SimpleNamespace(
        last_update_success=True,
        data={},
        consecutive_empty_updates=EMPTY_DEVICE_LIMIT,
        update_interval=timedelta(seconds=POLL_UPGRADE),
        empty_since=dt_util.utcnow() - timedelta(hours=1, seconds=1),
    )
    assert not device_removal_is_confirmed(coordinator)  # type: ignore[arg-type]

    coordinator.consecutive_empty_updates = EMPTY_DEVICE_WINDOW // POLL_UPGRADE
    assert device_removal_is_confirmed(coordinator)  # type: ignore[arg-type]

    # Rapid refreshes cannot shorten the window, however many responses arrive.
    coordinator.empty_since = dt_util.utcnow() - timedelta(minutes=5)
    assert not device_removal_is_confirmed(coordinator)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("empty_updates", "orphan_removed"),
    [
        (1, False),
        (EMPTY_DEVICE_LIMIT - 1, False),
        # The minimum count alone is not enough, an hour has to pass
        (EMPTY_DEVICE_LIMIT, False),
        (EMPTY_DEVICE_LIMIT + 1, True),
    ],
)
async def test_cleanup_devices_requires_confirmed_empty_list(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    empty_updates: int,
    orphan_removed: bool,
) -> None:
    """Test device cleanup removes entries only after repeated empty responses."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    controller = hass.config_entries.async_get_entry(
        mock_config_entry.entry_id
    ).runtime_data

    orphan = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "99:99:99:99:99:99")},
        manufacturer="TP-Link",
        model="Test",
        name="Orphan",
    )

    site_client = mock_omada_client.get_site_client.return_value
    site_client.get_devices = AsyncMock(return_value=[])

    for _ in range(empty_updates):
        await _async_poll_devices(hass, freezer)
        await async_cleanup_devices(hass, controller)

    assert (device_registry.async_get(orphan.id) is None) is orphan_removed


async def test_cleanup_keeps_devices_after_failed_poll(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed device poll leaves the cached device list untouched."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    orphan = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "99:99:99:99:99:99")},
        manufacturer="TP-Link",
        model="Test",
        name="Orphan",
    )

    # The cached device list is still populated from setup, but the poll fails
    site_client = mock_omada_client.get_site_client.return_value
    site_client.get_devices = AsyncMock(side_effect=OmadaClientException)
    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    assert device_registry.async_get(orphan.id) is not None


async def test_cleanup_devices_empty_count_resets_on_data(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the empty sweep counter resets when devices are reported again."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    controller = hass.config_entries.async_get_entry(
        mock_config_entry.entry_id
    ).runtime_data

    switch_mac = "54-AF-97-00-00-01"
    site_client = mock_omada_client.get_site_client.return_value

    site_client.get_devices = AsyncMock(return_value=[])
    await _async_poll_devices(hass, freezer)
    await async_cleanup_devices(hass, controller)
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, switch_mac), mock_config_entry.entry_id
    )

    devices_data = await async_load_json_array_fixture(hass, "devices.json", DOMAIN)
    site_client.get_devices = AsyncMock(
        return_value=[OmadaListDevice(d) for d in devices_data]
    )
    await _async_poll_devices(hass, freezer)
    await async_cleanup_devices(hass, controller)
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, switch_mac), mock_config_entry.entry_id
    )

    # A reported device must clear the streak rather than only keep it low.
    assert controller.devices_coordinator.consecutive_empty_updates == 0

    site_client.get_devices = AsyncMock(return_value=[])
    await _async_poll_devices(hass, freezer)
    await async_cleanup_devices(hass, controller)
    assert controller.devices_coordinator.consecutive_empty_updates == 1
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, switch_mac), mock_config_entry.entry_id
    )


@pytest.mark.parametrize(
    "poll_failure",
    [
        pytest.param(OmadaClientException, id="api_error"),
        pytest.param(TimeoutError, id="timeout"),
    ],
)
async def test_cleanup_devices_empty_count_resets_on_failure(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    poll_failure: type[Exception],
) -> None:
    """Test a failed poll stops empty responses from accumulating."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    controller = hass.config_entries.async_get_entry(
        mock_config_entry.entry_id
    ).runtime_data

    switch_mac = "54-AF-97-00-00-01"
    site_client = mock_omada_client.get_site_client.return_value

    site_client.get_devices = AsyncMock(return_value=[])
    for _ in range(EMPTY_DEVICE_LIMIT - 1):
        await _async_poll_devices(hass, freezer)
        await async_cleanup_devices(hass, controller)

    site_client.get_devices = AsyncMock(side_effect=poll_failure)
    await _async_poll_devices(hass, freezer)
    await async_cleanup_devices(hass, controller)
    assert controller.devices_coordinator.consecutive_empty_updates == 0
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, switch_mac), mock_config_entry.entry_id
    )

    site_client.get_devices = AsyncMock(return_value=[])
    await _async_poll_devices(hass, freezer)
    await async_cleanup_devices(hass, controller)
    assert controller.devices_coordinator.consecutive_empty_updates == 1
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, switch_mac), mock_config_entry.entry_id
    )


async def test_cleanup_skipped_when_polling_disabled(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the hourly cleanup does not poll while polling is disabled."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, pref_disable_polling=True)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    site_client = mock_omada_clients_only_client.get_site_client.return_value
    calls_before = site_client.get_devices.call_count

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=1, seconds=1))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert site_client.get_devices.call_count == calls_before


async def test_unload_cancels_cleanup_and_interval(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entry unload cancels in-flight cleanup task and removes interval."""
    cleanup_started = asyncio.Event()
    cleanup_cancelled = False
    cleanup_calls = 0

    async def blocking_cleanup(h: HomeAssistant, c: OmadaSiteController) -> None:
        nonlocal cleanup_cancelled, cleanup_calls
        cleanup_calls += 1
        if cleanup_calls == 1:
            # The startup sweep runs during setup, before platforms are added
            return
        cleanup_started.set()
        try:
            await asyncio.Event().wait()  # block forever until cancelled
        except asyncio.CancelledError:
            cleanup_cancelled = True
            raise

    with patch(
        "homeassistant.components.tplink_omada.async_cleanup_devices",
        new=blocking_cleanup,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Start the hourly cleanup task and leave it in flight
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=1, seconds=1))
        await hass.async_block_till_done()
        assert cleanup_started.is_set()

        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert cleanup_cancelled is True
        assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

        # Firing the interval after unload must not start a new cleanup task.
        # This stays inside the patch, so a leaked interval would be visible.
        cleanup_started.clear()
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=2, seconds=1))
        await hass.async_block_till_done(wait_background_tasks=True)
        assert not cleanup_started.is_set()


async def test_migrate_entry_v1_to_v2(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
) -> None:
    """Test migration of a version 1 config entry to version 2."""
    entry = MockConfigEntry(
        title="Test Omada Controller",
        domain=DOMAIN,
        data=dict(MOCK_ENTRY_DATA),
        unique_id="12345",
        version=1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 2
    assert entry.unique_id == "12345_SiteId"
    assert entry.state is ConfigEntryState.LOADED
