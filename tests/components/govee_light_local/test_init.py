"""Tests init for the Govee Local API integration."""

import asyncio
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from govee_local_api import GoveeDevice
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant import config_entries
from homeassistant.components.govee_light_local.const import (
    CLEANUP_TIMEOUT,
    CLEANUP_WAIT_TIMEOUT,
    CONF_MANUAL_DEVICES,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import (
    DEFAULT_CAPABILITIES,
    DISABLED_NETWORK_ADAPTERS,
    set_mocked_devices,
    setup_light,
)


async def test_setup_entry_with_options(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test configured manual devices are queued for discovery at setup."""

    # Setup waits for discovery to find a device, so seed one that answered.
    discovered = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.50",
        fingerprint="discovered-fingerprint",
        sku="H615B",
        capabilities=DEFAULT_CAPABILITIES,
    )
    set_mocked_devices(mock_govee_api, [discovered])

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_MANUAL_DEVICES: ["192.168.1.100"],
        },
    )

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_govee_api.add_device_to_discovery_queue.assert_called_once_with(
        "192.168.1.100"
    )


async def test_update_options_remove_device_discovered(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a discovered manual device is removed when dropped from options."""

    manual_device1 = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.100",
        fingerprint="manual_device1-fingerprint",
        sku="H615A",
        capabilities=DEFAULT_CAPABILITIES,
    )
    manual_device1.is_manual = True
    manual_device2 = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.101",
        fingerprint="manual_device2-fingerprint",
        sku="H615B",
        capabilities=DEFAULT_CAPABILITIES,
    )
    manual_device2.is_manual = True
    set_mocked_devices(mock_govee_api, [manual_device1, manual_device2])

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_MANUAL_DEVICES: [manual_device1.ip, manual_device2.ip],
        },
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is config_entries.ConfigEntryState.LOADED
    assert entity_registry.async_get("light.h615a") is not None
    assert entity_registry.async_get("light.h615b") is not None

    # Dropping the IP from the desired set is the whole removal instruction.
    hass.config_entries.async_update_entry(
        config_entry,
        options={
            CONF_MANUAL_DEVICES: [manual_device2.ip],
        },
    )
    set_mocked_devices(mock_govee_api, [manual_device2])
    await hass.async_block_till_done()

    assert config_entry.state is config_entries.ConfigEntryState.LOADED
    mock_govee_api.remove_device_from_discovery_queue.assert_called_once_with(
        manual_device1.ip
    )
    assert entity_registry.async_get("light.h615b") is not None
    assert entity_registry.async_get("light.h615a") is None


async def test_update_options_remove_multiple_devices(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test removing several devices in a single options update.

    The remove form allows multiple selections, so the listener has to cope
    with more than one device disappearing at once.
    """

    devices = []
    for index, (ip, sku) in enumerate(
        [("192.168.1.100", "H615A"), ("192.168.1.101", "H615B")]
    ):
        device = GoveeDevice(
            controller=mock_govee_api,
            ip=ip,
            fingerprint=f"manual_device{index}-fingerprint",
            sku=sku,
            capabilities=DEFAULT_CAPABILITIES,
        )
        device.is_manual = True
        devices.append(device)
    set_mocked_devices(mock_govee_api, devices)

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_MANUAL_DEVICES: [device.ip for device in devices],
        },
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get("light.h615a") is not None
    assert entity_registry.async_get("light.h615b") is not None

    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_MANUAL_DEVICES: []},
    )
    set_mocked_devices(mock_govee_api, [])
    await hass.async_block_till_done()

    assert config_entry.state is config_entries.ConfigEntryState.LOADED
    assert mock_govee_api.remove_device_from_discovery_queue.call_count == 2
    # The options are the source of truth; the listener must not rewrite them.
    assert config_entry.options == {
        CONF_MANUAL_DEVICES: [],
    }
    assert entity_registry.async_get("light.h615a") is None
    assert entity_registry.async_get("light.h615b") is None


async def test_update_options_remove_device_in_queue(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test removing a manual device that was never discovered."""

    manual_device1 = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.100",
        fingerprint="manual_device1-fingerprint",
        sku="H615A",
        capabilities=DEFAULT_CAPABILITIES,
    )
    manual_device1.is_manual = True
    set_mocked_devices(mock_govee_api, [manual_device1])

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_MANUAL_DEVICES: [manual_device1.ip],
        },
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Queue an IP that never answers, then drop it again.
    hass.config_entries.async_update_entry(
        config_entry,
        options={
            CONF_MANUAL_DEVICES: [manual_device1.ip, "192.168.1.101"],
        },
    )
    await hass.async_block_till_done()
    assert "192.168.1.101" in mock_govee_api.discovery_queue

    hass.config_entries.async_update_entry(
        config_entry,
        options={
            CONF_MANUAL_DEVICES: [manual_device1.ip],
        },
    )
    await hass.async_block_till_done()

    assert config_entry.state is config_entries.ConfigEntryState.LOADED
    assert "192.168.1.101" not in mock_govee_api.discovery_queue
    # The already-discovered device is untouched.
    assert len(hass.states.async_all()) == 1


async def test_update_options_add_devices(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test adding multiple devices via options."""

    device1 = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.100",
        fingerprint="device1-fingerprint",
        sku="H615A",
        capabilities=DEFAULT_CAPABILITIES,
    )
    device1.is_manual = True

    device2 = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.101",
        fingerprint="device2-fingerprint",
        sku="H6199",
        capabilities=DEFAULT_CAPABILITIES,
    )
    device2.is_manual = True

    # Setup waits for discovery to find a device, so seed one that answered.
    discovered = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.50",
        fingerprint="discovered-fingerprint",
        sku="H615C",
        capabilities=DEFAULT_CAPABILITIES,
    )
    set_mocked_devices(mock_govee_api, [discovered])

    config_entry = MockConfigEntry(domain=DOMAIN)

    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    set_mocked_devices(mock_govee_api, [device1])
    mock_govee_api.get_device_by_ip.side_effect = [None, device1]

    hass.config_entries.async_update_entry(
        config_entry,
        options={
            CONF_MANUAL_DEVICES: [device1.ip],
        },
    )

    await hass.async_block_till_done()

    mock_govee_api.add_device_to_discovery_queue.assert_called_once_with(device1.ip)


async def test_setup_without_listening_addresses(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test setup is retried when no enabled adapter has an IPv4 address."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.network.async_get_adapters",
        return_value=DISABLED_NETWORK_ADAPTERS,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is config_entries.ConfigEntryState.SETUP_RETRY
    assert (
        config_entry.reason
        == "No enabled network adapter has an IPv4 address to listen on"
    )
    mock_govee_api.start.assert_not_awaited()


@pytest.mark.usefixtures("mock_network_adapters")
async def test_unload_releases_port(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test unloading waits for the controller to release the listening port."""

    entry, _ = await setup_light(hass, mock_govee_api)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
    mock_govee_api.cleanup.assert_called_once_with(timeout=CLEANUP_TIMEOUT)


@pytest.mark.usefixtures("mock_network_adapters", "mock_stuck_cleanup")
async def test_unload_waits_for_delayed_cleanup(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test unloading keeps waiting for a cleanup that completes late."""

    entry, _ = await setup_light(hass, mock_govee_api)

    unload_task = hass.async_create_task(
        hass.config_entries.async_unload(entry.entry_id)
    )
    await asyncio.sleep(0)
    assert not unload_task.done()

    # Two seconds in: inside the cleanup wait window, so unload is still pending.
    freezer.tick(2)
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert not unload_task.done()

    mock_govee_api.cleanup.return_value.set()
    assert await unload_task

    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
    assert "Timed out waiting for port" not in caplog.text


@pytest.mark.usefixtures("mock_network_adapters", "mock_stuck_cleanup")
async def test_unload_warns_when_port_not_released(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a controller that never closes its sockets does not wedge the unload."""

    entry, _ = await setup_light(hass, mock_govee_api)

    unload_task = hass.async_create_task(
        hass.config_entries.async_unload(entry.entry_id)
    )
    await asyncio.sleep(0)

    freezer.tick(CLEANUP_WAIT_TIMEOUT + 1)
    await asyncio.sleep(0)
    assert await unload_task
    await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
    assert "Timed out waiting for port 4002 to be released" in caplog.text


@pytest.mark.parametrize(
    ("initial_manual_devices", "is_manual", "expected_manual_devices"),
    [
        pytest.param(
            ["192.168.1.100", "192.168.1.101"],
            True,
            ["192.168.1.101"],
            id="configured_device_is_unconfigured",
        ),
        pytest.param(
            ["192.168.1.101"],
            False,
            ["192.168.1.101"],
            id="discovered_device_leaves_options_alone",
        ),
    ],
)
async def test_remove_device_from_device_page(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_govee_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
    initial_manual_devices: list[str],
    is_manual: bool,
    expected_manual_devices: list[str],
) -> None:
    """Test deleting a device from the device page.

    Deletion always succeeds and always makes the controller forget the device,
    otherwise its next scan reply is reported as an already known device and no
    entity is ever recreated. The listener keys off whether the IP is
    configured, so a configured device is also unconfigured (otherwise the
    reconcile would re-add it), while a purely discovered one leaves the
    options untouched.
    """
    assert await async_setup_component(hass, "config", {})

    device = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.100",
        fingerprint="asdawdqwdqwd",
        sku="H615A",
        capabilities=DEFAULT_CAPABILITIES,
    )
    device.is_manual = is_manual
    # A second device confirms only the deleted one is affected.
    other = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.101",
        fingerprint="other-fingerprint",
        sku="H615B",
        capabilities=DEFAULT_CAPABILITIES,
    )
    other.is_manual = True
    set_mocked_devices(mock_govee_api, [device, other])

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_MANUAL_DEVICES: initial_manual_devices,
        },
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, device.fingerprint), config_entry.entry_id
    )
    assert device_entry is not None

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "config/device_registry/remove", "device_id": device_entry.id}
    )
    response = await client.receive_json()
    await hass.async_block_till_done()

    assert response["success"]
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, device.fingerprint), config_entry.entry_id
        )
        is None
    )
    mock_govee_api.remove_device.assert_called_once_with(device)
    assert config_entry.options[CONF_MANUAL_DEVICES] == expected_manual_devices
    # The other device is left alone either way.
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, other.fingerprint), config_entry.entry_id
        )
        is not None
    )
    assert mock_govee_api.get_device_by_fingerprint(device.fingerprint) is None


async def test_removed_discovered_device_returns_on_next_scan(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_govee_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a deleted discovered device is re-added by the next discovery.

    The controller must forget the device on deletion. If it does not, the
    device keeps answering discovery but is reported as already known, so the
    platform never recreates the entity and the light stays missing until the
    entry is reloaded.
    """
    assert await async_setup_component(hass, "config", {})

    device = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.100",
        fingerprint="asdawdqwdqwd",
        sku="H615A",
        capabilities=DEFAULT_CAPABILITIES,
    )
    set_mocked_devices(mock_govee_api, [device])

    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, device.fingerprint), config_entry.entry_id
    )
    assert device_entry is not None
    assert hass.states.get("light.H615A") is not None

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "config/device_registry/remove", "device_id": device_entry.id}
    )
    response = await client.receive_json()
    await hass.async_block_till_done()

    assert response["success"]
    mock_govee_api.remove_device.assert_called_once_with(device)
    # Until the device answers again it stays gone, entity included.
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, device.fingerprint), config_entry.entry_id
        )
        is None
    )
    assert hass.states.get("light.H615A") is None

    # The library builds a fresh device for a fingerprint it no longer knows,
    # so the next scan reply arrives as a new discovery.
    rediscovered = GoveeDevice(
        controller=mock_govee_api,
        ip=device.ip,
        fingerprint=device.fingerprint,
        sku=device.sku,
        capabilities=DEFAULT_CAPABILITIES,
    )
    set_mocked_devices(mock_govee_api, [rediscovered])

    discovery_callback = mock_govee_api.set_device_discovered_callback.call_args[0][0]
    assert discovery_callback(rediscovered, True) is True
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, device.fingerprint), config_entry.entry_id
        )
        is not None
    )
    assert hass.states.get("light.H615A") is not None


async def test_remove_device_of_other_entry_is_ignored(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a removal belonging to another entry leaves our options alone."""
    device = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.100",
        fingerprint="asdawdqwdqwd",
        sku="H615A",
        capabilities=DEFAULT_CAPABILITIES,
    )
    device.is_manual = True
    set_mocked_devices(mock_govee_api, [device])

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_MANUAL_DEVICES: ["192.168.1.100"],
        },
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Same identifier, different config entry: the listener must ignore it.
    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    other_device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={(DOMAIN, device.fingerprint)},
    )
    device_registry.async_remove_device(other_device.id)
    await hass.async_block_till_done()

    assert config_entry.options[CONF_MANUAL_DEVICES] == ["192.168.1.100"]
