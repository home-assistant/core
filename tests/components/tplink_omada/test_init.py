"""Tests for TP-Link Omada integration init."""

import asyncio
from collections.abc import AsyncGenerator
from copy import deepcopy
from datetime import timedelta
from functools import partial
import logging
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
    async_load_json_object_fixture,
)
from tplink_omada_client.clients import OmadaWiredClient, OmadaWirelessClient
from tplink_omada_client.devices import OmadaGateway, OmadaListDevice
from tplink_omada_client.exceptions import (
    ConnectionFailed,
    LoginFailed,
    OmadaClientException,
    UnsupportedControllerVersion,
)

from homeassistant.components.tplink_omada import (
    OmadaConfigEntry,
    async_remove_config_entry_device,
)
from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.components.tplink_omada.coordinator import (
    POLL_CLIENTS,
    POLL_GATEWAY,
    POLL_KNOWN_CLIENTS,
    OmadaCoordinator,
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


async def test_gateway_invalidate_discards_inflight_refresh(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a gateway poll started before a removal cannot restore stale data."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    gateway_mac = "AA-BB-CC-DD-EE-FF"
    port_entity_id = "switch.test_router_port_12_poe"
    site_client = mock_omada_client.get_site_client.return_value
    assert hass.states.get(port_entity_id) is not None

    # A poll that started before the removal reports the gateway without port 12.
    gateway_data = await async_load_json_object_fixture(
        hass, "gateway-TL-ER7212PC.json", DOMAIN
    )
    stale_data = deepcopy(gateway_data)
    stale_data["portConfigs"] = [
        port for port in stale_data["portConfigs"] if port["port"] != 12
    ]
    started = asyncio.Event()
    release = asyncio.Event()

    async def _stale_get_gateway(mac: str) -> object:
        started.set()
        await release.wait()
        return OmadaGateway(stale_data)

    site_client.get_gateway = _stale_get_gateway

    freezer.tick(timedelta(seconds=POLL_GATEWAY + 1))
    async_fire_time_changed(hass, dt_util.utcnow())
    for _ in range(50):
        if started.is_set():
            break
        await asyncio.sleep(0)
    assert started.is_set()

    # The gateway is removed while that poll is still running.
    gateway_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, gateway_mac), mock_config_entry.entry_id
    )
    assert gateway_device is not None
    assert await async_remove_config_entry_device(
        hass, cast(OmadaConfigEntry, mock_config_entry), gateway_device
    )
    device_registry.async_remove_device(gateway_device.id)
    assert hass.states.get(port_entity_id) is None

    # The stale result arrives after the removal and must be dropped.
    release.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    # The gateway returns, but its next poll fails. If the dropped result had
    # been kept, registration would rebuild entities from it; it must not.
    site_client.get_gateway = AsyncMock(
        side_effect=OmadaClientException("gateway unavailable")
    )
    devices_data = await async_load_json_array_fixture(hass, "devices.json", DOMAIN)
    site_client.get_devices = AsyncMock(
        return_value=[OmadaListDevice(device) for device in devices_data]
    )
    await _async_poll_devices(hass, freezer)

    assert hass.states.get(port_entity_id) is None
    assert not [
        entry
        for entry in entity_registry.entities.values()
        if entry.platform == DOMAIN
        and entry.domain in {"binary_sensor", "switch"}
        and entry.unique_id.startswith(f"{gateway_mac}_")
        and "_vpn_" not in entry.unique_id
    ]


async def test_automatic_missing_device_cleanup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_omada_client: MagicMock,
) -> None:
    """Test missing devices are removed during setup and the controller is kept."""
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
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "00-11-22-33-44-55"), mock_config_entry.entry_id
    )
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "54-AF-97-00-00-01"), mock_config_entry.entry_id
    )


async def test_remove_config_entry_device(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test users can remove a site device but not the controller."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    entry = cast(OmadaConfigEntry, mock_config_entry)

    switch_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "54-AF-97-00-00-01"), mock_config_entry.entry_id
    )
    controller_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "00-11-22-33-44-55"), mock_config_entry.entry_id
    )
    assert switch_device is not None
    assert controller_device is not None

    assert await async_remove_config_entry_device(hass, entry, switch_device)
    assert not await async_remove_config_entry_device(hass, entry, controller_device)

    # A manual removal survives an empty controller response: the cached device
    # list was pruned, so registration does not recreate the device.
    device_registry.async_remove_device(switch_device.id)
    site_client = mock_omada_client.get_site_client.return_value
    site_client.get_devices = AsyncMock(return_value=[])
    await _async_poll_devices(hass, freezer)
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "54-AF-97-00-00-01"), mock_config_entry.entry_id
        )
        is None
    )

    # The removal API can be called after unload, when runtime data is gone.
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not await async_remove_config_entry_device(hass, entry, controller_device)


async def test_in_flight_registration_skips_removed_device(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a callback finishing after removal cannot recreate the device."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    site_client = mock_omada_client.get_site_client.return_value
    switch_mac = "54-AF-97-00-00-01"
    original_get_devices = site_client.get_devices

    # Remove the switch so its entities and registration state are gone.
    site_client.get_devices = AsyncMock(
        side_effect=partial(_get_devices_without, hass, switch_mac)
    )
    await _async_poll_devices(hass, freezer)
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, switch_mac), mock_config_entry.entry_id
        )
        is None
    )

    # Block the reappearance registration inside get_switch.
    started = asyncio.Event()
    release = asyncio.Event()
    original_get_switch = site_client.get_switch

    async def _slow_get_switch(device: OmadaListDevice) -> object:
        started.set()
        await release.wait()
        return await original_get_switch(device)

    site_client.get_switch = _slow_get_switch
    site_client.get_devices = original_get_devices

    freezer.tick(timedelta(seconds=POLL_CLIENTS + 1))
    async_fire_time_changed(hass, dt_util.utcnow())
    for _ in range(50):
        if started.is_set():
            break
        await asyncio.sleep(0)
    assert started.is_set()
    port_polls = site_client.get_switch_ports.call_count

    # Remove the switch again while the callback is still awaiting the client.
    switch_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, switch_mac), mock_config_entry.entry_id
    )
    assert switch_device is not None
    assert await async_remove_config_entry_device(
        hass, cast(OmadaConfigEntry, mock_config_entry), switch_device
    )
    device_registry.async_remove_device(switch_device.id)

    release.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    # The callback must not fetch ports or create entities for the removed
    # switch, and it must not leave a port coordinator behind for it.
    assert site_client.get_switch_ports.call_count == port_polls
    assert hass.states.get("switch.test_poe_switch_port_1_poe") is None
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, switch_mac), mock_config_entry.entry_id
        )
        is None
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


async def test_device_update_removes_disappeared_device(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a device-list update removes the devices it no longer reports."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    removed_mac = "54-AF-97-00-00-01"
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, removed_mac), mock_config_entry.entry_id
    )

    site_client = mock_omada_client.get_site_client.return_value
    site_client.get_devices = AsyncMock(
        side_effect=partial(_get_devices_without, hass, removed_mac)
    )
    await _async_poll_devices(hass, freezer)

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, removed_mac), mock_config_entry.entry_id
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id("update", DOMAIN, f"{removed_mac}_firmware")
        is None
    )


async def test_empty_device_update_keeps_devices(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an empty device list is treated as a glitch and removes nothing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    switch_mac = "54-AF-97-00-00-01"
    sensor_entity_id = "sensor.test_poe_switch_device_status"
    assert hass.states.get(sensor_entity_id) is not None

    site_client = mock_omada_client.get_site_client.return_value
    site_client.get_devices = AsyncMock(return_value=[])
    await _async_poll_devices(hass, freezer)

    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, switch_mac), mock_config_entry.entry_id
    )
    assert (
        entity_registry.async_get_entity_id("update", DOMAIN, f"{switch_mac}_firmware")
        is not None
    )
    assert hass.states.get(sensor_entity_id) is not None
    assert hass.states.get(sensor_entity_id).state not in {"unknown", "unavailable"}


async def test_cleanup_removes_startup_stale_device_after_empty_startup(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a stale entry is removed once a populated poll follows an empty startup."""
    mock_config_entry.add_to_hass(hass)

    stale_mac = "99:99:99:99:99:99"
    stale_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, stale_mac)},
        manufacturer="TP-Link",
        model="Test",
        name="Old Device",
    )

    site_client = mock_omada_client.get_site_client.return_value
    original_get_devices = site_client.get_devices
    site_client.get_devices = AsyncMock(return_value=[])

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    # The empty startup list skipped the sweep, so the stale entry survives.
    assert device_registry.async_get(stale_device.id) is not None

    # The first populated poll sweeps, because nothing was seeded yet.
    site_client.get_devices = original_get_devices
    await _async_poll_devices(hass, freezer)

    assert device_registry.async_get(stale_device.id) is None


async def test_failed_poll_keeps_devices(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failed device poll removes nothing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    switch_mac = "54-AF-97-00-00-01"
    site_client = mock_omada_client.get_site_client.return_value
    site_client.get_devices = AsyncMock(side_effect=OmadaClientException)
    await _async_poll_devices(hass, freezer)

    assert "Error fetching Omada API Data - DeviceList data" in caplog.text
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, switch_mac), mock_config_entry.entry_id
    )


async def test_registration_failure_is_logged_and_retried(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a transient switch fetch failure is logged and registration retries."""
    mock_config_entry.add_to_hass(hass)

    site_client = mock_omada_client.get_site_client.return_value
    original_get_switch = site_client.get_switch.return_value
    fail_switch_fetch = True

    async def _get_switch(device: OmadaListDevice) -> object:
        if fail_switch_fetch:
            raise OmadaClientException("switch fetch failed")
        return original_get_switch

    site_client.get_switch = AsyncMock(side_effect=_get_switch)

    with caplog.at_level(
        logging.DEBUG, logger="homeassistant.components.tplink_omada.controller"
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert "Failed to register entities for Omada device" in caplog.text
    assert "switch fetch failed" in caplog.text
    assert hass.states.get("switch.test_poe_switch_port_1_poe") is None

    # The failed device was left unprocessed, so the next update retries.
    fail_switch_fetch = False
    await _async_poll_devices(hass, freezer)

    assert hass.states.get("switch.test_poe_switch_port_1_poe") is not None


async def test_switch_port_refresh_failure_is_retried(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed switch port refresh defers registration to the next update."""
    site_client = mock_omada_client.get_site_client.return_value
    original_get_switch_ports = site_client.get_switch_ports
    site_client.get_switch_ports = AsyncMock(side_effect=OmadaClientException)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("switch.test_poe_switch_port_1_poe") is None

    # The failed refresh left the switch unprocessed, so the next update retries.
    site_client.get_switch_ports = original_get_switch_ports
    await _async_poll_devices(hass, freezer)

    assert hass.states.get("switch.test_poe_switch_port_1_poe") is not None


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


async def test_cleanup_recreates_device_when_reappears(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a removed device is registered again when it returns."""
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

    # Remove the switch from the controller's device list
    site_client.get_devices = AsyncMock(
        side_effect=partial(_get_devices_without, hass, removed_mac)
    )
    await _async_poll_devices(hass, freezer)

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, removed_mac), mock_config_entry.entry_id
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id("update", DOMAIN, update_unique_id) is None
    )

    # Switch returns to the controller, and the next poll registers it again
    devices_data = await async_load_json_array_fixture(hass, "devices.json", DOMAIN)
    site_client.get_devices = AsyncMock(
        return_value=[OmadaListDevice(d) for d in devices_data]
    )
    await _async_poll_devices(hass, freezer)

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
    """Test a returning gateway rebuilds only entities with valid data."""
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
            and "_vpn_" not in entry.unique_id
        ]

    vpn_entity_ids = (
        "switch.test_router_road_warriors",
        "switch.test_router_branch_office",
    )
    assert all(hass.states.get(entity_id) is not None for entity_id in vpn_entity_ids)
    assert gateway_port_entities()

    site_client = mock_omada_client.get_site_client.return_value

    # Remove the gateway from the controller's device list
    site_client.get_devices = AsyncMock(
        side_effect=partial(_get_devices_without, hass, gateway_mac)
    )
    await _async_poll_devices(hass, freezer)

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, gateway_mac), mock_config_entry.entry_id
        )
        is None
    )
    assert not gateway_port_entities()
    assert all(hass.states.get(entity_id) is None for entity_id in vpn_entity_ids)

    # The gateway returns, but its refresh fails: no port entities are built
    # from the cached port lists, and registration stays retryable. VPN policy
    # switches are rebuilt because their coordinator data is still valid.
    site_client.get_gateway = AsyncMock(
        side_effect=OmadaClientException("gateway unavailable")
    )
    devices_data = await async_load_json_array_fixture(hass, "devices.json", DOMAIN)
    site_client.get_devices = AsyncMock(
        return_value=[OmadaListDevice(device) for device in devices_data]
    )
    await _async_poll_devices(hass, freezer)

    assert not gateway_port_entities()
    assert all(hass.states.get(entity_id) is not None for entity_id in vpn_entity_ids)

    # A successful refresh rebuilds the port entities.
    gateway_data = await async_load_json_object_fixture(
        hass, "gateway-TL-ER7212PC.json", DOMAIN
    )
    site_client.get_gateway = AsyncMock(return_value=OmadaGateway(gateway_data))
    await _async_poll_devices(hass, freezer)

    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, gateway_mac), mock_config_entry.entry_id
    )
    assert gateway_port_entities()


async def test_automatic_missing_client_cleanup(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test missing client trackers are removed during initial startup cleanup.

    The known-clients coordinator sweeps the registry on its first refresh,
    which runs before the device tracker platform is set up.
    """

    mock_config_entry = MockConfigEntry(
        title="Test Omada Controller",
        domain=DOMAIN,
        data=dict(MOCK_ENTRY_DATA),
        unique_id="12345",
    )
    mock_config_entry.add_to_hass(hass)

    tracker = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_SiteId_11-11-11-11-11-11",
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )

    assert entity_registry.async_get(tracker.entity_id)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entity_registry.async_get(tracker.entity_id) is None


async def test_cleanup_removes_unknown_integration_disabled_tracker(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an unknown tracker disabled by the integration is removed."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    unknown_client = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_Default_99-99-99-99-99-99",
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )

    site_client = mock_omada_clients_only_client.get_site_client.return_value
    site_client.get_known_clients.side_effect = partial(
        _get_known_clients_without, hass, ""
    )
    await _async_poll_known_clients(hass, freezer)

    assert entity_registry.async_get(unknown_client.entity_id) is None


@pytest.mark.parametrize(
    ("domain", "unique_id", "disabled_by"),
    [
        pytest.param(
            "device_tracker",
            "scanner_Default_66-66-66-66-66-66",
            None,
            id="enabled-unknown-tracker",
        ),
        pytest.param(
            "device_tracker",
            "scanner_Default_77-77-77-77-77-77",
            er.RegistryEntryDisabler.USER,
            id="user-disabled-tracker",
        ),
        pytest.param("sensor", "some_sensor", None, id="other-domain"),
        pytest.param(
            "device_tracker",
            "tracker_00-11-22-33-44-55",
            er.RegistryEntryDisabler.INTEGRATION,
            id="unowned-tracker",
        ),
    ],
)
async def test_cleanup_keeps_entries_it_does_not_own(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    domain: str,
    unique_id: str,
    disabled_by: er.RegistryEntryDisabler | None,
) -> None:
    """Test the cleanup leaves entries it does not own alone."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = entity_registry.async_get_or_create(
        domain=domain,
        platform=DOMAIN,
        unique_id=unique_id,
        config_entry=mock_config_entry,
        disabled_by=disabled_by,
    )

    site_client = mock_omada_clients_only_client.get_site_client.return_value
    site_client.get_known_clients.side_effect = partial(
        _get_known_clients_without, hass, ""
    )
    await _async_poll_known_clients(hass, freezer)

    assert entity_registry.async_get(entity.entity_id) is not None


async def _get_known_clients_without(
    hass: HomeAssistant, excluded_mac: str
) -> AsyncGenerator[OmadaWirelessClient]:
    """Yield wireless clients from the known-clients fixture, skipping one MAC."""
    known_clients_data = await async_load_json_array_fixture(
        hass, "known-clients.json", DOMAIN
    )
    for client in known_clients_data:
        if client["mac"] != excluded_mac and client["wireless"]:
            yield OmadaWirelessClient(client)


async def _get_no_known_clients() -> AsyncGenerator[OmadaWirelessClient]:
    """Yield no known clients."""
    for client in ():
        yield client


async def _get_wired_known_clients(
    hass: HomeAssistant,
) -> AsyncGenerator[OmadaWiredClient]:
    """Yield only wired clients from the known-clients fixture."""
    known_clients_data = await async_load_json_array_fixture(
        hass, "known-clients.json", DOMAIN
    )
    for client in known_clients_data:
        if not client["wireless"]:
            yield OmadaWiredClient(client)


async def _async_poll_known_clients(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Advance to the next known clients poll and let it complete."""
    freezer.tick(timedelta(seconds=POLL_KNOWN_CLIENTS + 1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_client_cleanup_removes_trackers_for_unknown_clients(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a client removed from the controller is cleaned up on the next poll."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Client present in the known-clients.json fixture at startup
    removed_mac = "2C-71-FF-ED-34-83"
    tracker = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id=f"scanner_Default_{removed_mac}",
        config_entry=mock_config_entry,
    )
    assert tracker.device_id is not None
    device_id = tracker.device_id

    # Remove the client from the controller's known-clients list
    site_client = mock_omada_clients_only_client.get_site_client.return_value
    site_client.get_known_clients.side_effect = partial(
        _get_known_clients_without, hass, removed_mac
    )
    await _async_poll_known_clients(hass, freezer)

    assert entity_registry.async_get(tracker.entity_id) is None
    assert device_registry.async_get(device_id) is None


async def test_cleanup_keeps_shared_device(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a stale tracker is removed without deleting a shared device."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    removed_mac = "2C-71-FF-ED-34-83"
    tracker_entity_id = entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, f"scanner_Default_{removed_mac}"
    )
    assert tracker_entity_id is not None
    tracker = entity_registry.async_get(tracker_entity_id)
    assert tracker is not None
    assert tracker.device_id is not None
    device_id = tracker.device_id

    shared_entity = entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="shared_device_sensor",
        config_entry=mock_config_entry,
        device_id=device_id,
    )

    site_client = mock_omada_clients_only_client.get_site_client.return_value
    site_client.get_known_clients.side_effect = partial(
        _get_known_clients_without, hass, removed_mac
    )
    await _async_poll_known_clients(hass, freezer)

    assert entity_registry.async_get(tracker.entity_id) is None
    assert entity_registry.async_get(shared_entity.entity_id) is not None
    assert device_registry.async_get(device_id) is not None


async def test_cleanup_preserves_trackers_when_known_clients_fetch_fails(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test cleanup keeps trackers when the known clients fetch fails."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    stale_tracker = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_Default_99-99-99-99-99-99",
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )

    site_client = mock_omada_clients_only_client.get_site_client.return_value
    site_client.get_known_clients.side_effect = OmadaClientException("boom")
    await _async_poll_known_clients(hass, freezer)
    site_client.get_known_clients.assert_called()
    assert "Error fetching Omada API Data - KnownClientsList data" in caplog.text
    assert entity_registry.async_get(stale_tracker.entity_id) is not None

    # A successful fetch lets the next poll remove the stale tracker
    site_client.get_known_clients.side_effect = partial(
        _get_known_clients_without, hass, ""
    )
    await _async_poll_known_clients(hass, freezer)
    assert entity_registry.async_get(stale_tracker.entity_id) is None


async def test_cleanup_recreates_tracker_when_client_reappears(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a tracker removed by cleanup is recreated when the client returns."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    removed_mac = "2C-71-FF-ED-34-83"
    tracker_unique_id = f"scanner_Default_{removed_mac}"
    site_client = mock_omada_clients_only_client.get_site_client.return_value

    # Remove the client from the controller's known-clients list and clean up
    site_client.get_known_clients.side_effect = partial(
        _get_known_clients_without, hass, removed_mac
    )
    await _async_poll_known_clients(hass, freezer)
    assert (
        entity_registry.async_get_entity_id("device_tracker", DOMAIN, tracker_unique_id)
        is None
    )

    # Client returns to the controller — the next poll recreates the tracker
    site_client.get_known_clients.side_effect = partial(
        _get_known_clients_without, hass, ""
    )
    await _async_poll_known_clients(hass, freezer)
    assert (
        entity_registry.async_get_entity_id("device_tracker", DOMAIN, tracker_unique_id)
        is not None
    )


async def test_startup_cleanup_runs_before_trackers_are_registered(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a stale tracker does not keep the entity ID of a same-named client."""
    mock_config_entry.add_to_hass(hass)

    stale_tracker = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_Default_11-11-11-11-11-11",
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
        suggested_object_id="banana",
    )
    assert stale_tracker.entity_id == "device_tracker.banana"

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        entity_registry.async_get_entity_id(
            "device_tracker", DOMAIN, "scanner_Default_2C-71-FF-ED-34-83"
        )
        == "device_tracker.banana"
    )


async def test_poll_cleanup_runs_before_trackers_are_registered(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the poll frees an entity ID before adding a same-named client."""
    banana_mac = "2C-71-FF-ED-34-83"
    site_client = mock_omada_clients_only_client.get_site_client.return_value
    site_client.get_known_clients.side_effect = partial(
        _get_known_clients_without, hass, banana_mac
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert (
        entity_registry.async_get_entity_id(
            "device_tracker", DOMAIN, f"scanner_Default_{banana_mac}"
        )
        is None
    )

    stale_tracker = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_Default_11-11-11-11-11-11",
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
        suggested_object_id="banana",
    )
    assert stale_tracker.entity_id == "device_tracker.banana"

    # The client becomes known again on the next poll
    site_client.get_known_clients.side_effect = partial(
        _get_known_clients_without, hass, ""
    )
    await _async_poll_known_clients(hass, freezer)

    assert (
        entity_registry.async_get_entity_id(
            "device_tracker", DOMAIN, f"scanner_Default_{banana_mac}"
        )
        == "device_tracker.banana"
    )


async def test_preserved_tracker_recreated_when_client_returns(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a preserved tracker is instantiated when its client returns."""
    mock_config_entry.add_to_hass(hass)

    client_mac = "2C-71-FF-ED-34-83"
    tracker = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id=f"scanner_Default_{client_mac}",
        config_entry=mock_config_entry,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(tracker.entity_id) is None

    # Client becomes known to the controller — the next poll instantiates the
    # preserved tracker
    site_client = mock_omada_client.get_site_client.return_value
    site_client.get_known_clients.side_effect = partial(
        _get_known_clients_without, hass, ""
    )
    await _async_poll_known_clients(hass, freezer)

    assert hass.states.get(tracker.entity_id) is not None


async def test_cleanup_keeps_trackers_on_empty_known_clients(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an empty known clients response is not treated as every client gone."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    removed_mac = "2C-71-FF-ED-34-83"
    tracker_entity_id = entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, f"scanner_Default_{removed_mac}"
    )
    assert tracker_entity_id is not None
    tracker = entity_registry.async_get(tracker_entity_id)
    assert tracker is not None

    site_client = mock_omada_clients_only_client.get_site_client.return_value
    site_client.get_known_clients.side_effect = None
    site_client.get_known_clients.return_value = _get_no_known_clients()

    # A successful but empty response is a controller glitch: keep the tracker.
    await _async_poll_known_clients(hass, freezer)

    assert entity_registry.async_get(tracker.entity_id) is not None


async def test_cleanup_runs_when_only_wired_clients_are_known(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a wired-only response still counts as a successful client poll."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    removed_mac = "2C-71-FF-ED-34-83"
    tracker_entity_id = entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, f"scanner_Default_{removed_mac}"
    )
    assert tracker_entity_id is not None
    tracker = entity_registry.async_get(tracker_entity_id)
    assert tracker is not None
    assert tracker.device_id is not None
    device_id = tracker.device_id

    site_client = mock_omada_clients_only_client.get_site_client.return_value
    site_client.get_known_clients.side_effect = partial(_get_wired_known_clients, hass)

    await _async_poll_known_clients(hass, freezer)

    assert entity_registry.async_get(tracker.entity_id) is None
    assert device_registry.async_get(device_id) is None


async def test_cleanup_keeps_tracker_for_known_client(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a tracker whose client is still known survives the sweep untouched."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    known_mac = "2C-71-FF-ED-34-83"
    tracker_entity_id = entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, f"scanner_Default_{known_mac}"
    )
    assert tracker_entity_id is not None
    tracker = entity_registry.async_get(tracker_entity_id)
    assert tracker is not None
    assert tracker.device_id is not None
    assert tracker.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    registry_id = tracker.id
    device_id = tracker.device_id
    device_modified_at = device_registry.async_get(device_id).modified_at

    # The mocked controller still reports this client, so the sweep keeps it.
    await _async_poll_known_clients(hass, freezer)

    kept_tracker = entity_registry.async_get(tracker_entity_id)
    assert kept_tracker is not None
    assert kept_tracker.id == registry_id
    assert kept_tracker.device_id == device_id
    kept_device = device_registry.async_get(device_id)
    assert kept_device is not None
    assert kept_device.modified_at == device_modified_at


async def test_repeat_poll_does_not_readd_known_trackers(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test unchanged known clients are not added to the platform again."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    known_mac = "2C-71-FF-ED-34-83"
    tracker_entity_id = entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, f"scanner_Default_{known_mac}"
    )
    assert tracker_entity_id is not None
    tracker = entity_registry.async_get(tracker_entity_id)
    assert tracker is not None
    registry_id = tracker.id

    # An enabled entity is instantiated, so a duplicate add is reported as an
    # error by the entity platform instead of being skipped silently.
    entity_registry.async_update_entity(tracker_entity_id, disabled_by=None)
    await hass.async_block_till_done()
    assert hass.states.get(tracker_entity_id) is not None

    caplog.clear()
    await _async_poll_known_clients(hass, freezer)
    await _async_poll_known_clients(hass, freezer)

    kept_tracker = entity_registry.async_get(tracker_entity_id)
    assert kept_tracker is not None
    assert kept_tracker.id == registry_id
    assert kept_tracker.disabled_by is None
    assert "does not generate unique IDs" not in caplog.text


async def test_cleanup_keeps_trackers_when_first_refresh_fails(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a failed known-clients first refresh removes nothing."""
    site_client = mock_omada_clients_only_client.get_site_client.return_value
    site_client.get_known_clients.side_effect = OmadaClientException("boom")

    mock_config_entry.add_to_hass(hass)
    stale_tracker = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_Default_99-99-99-99-99-99",
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert entity_registry.async_get(stale_tracker.entity_id) is not None


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
