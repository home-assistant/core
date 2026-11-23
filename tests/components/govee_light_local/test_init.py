"""Tests init for the Govee Local API integration."""

import asyncio
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from govee_local_api import GoveeDevice
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant import config_entries
from homeassistant.components.govee_light_local.const import (
    CLEANUP_TIMEOUT,
    CLEANUP_WAIT_TIMEOUT,
    CONF_DEVICE_IP,
    DOMAIN,
    SCAN_INTERVAL,
    SUBENTRY_TYPE_DEVICE,
)
from homeassistant.config_entries import ConfigSubentryData, SubentryFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import (
    DEFAULT_CAPABILITIES,
    DISABLED_NETWORK_ADAPTERS,
    set_mocked_devices,
    setup_light,
)


def _device_subentries(*ips: str) -> list[ConfigSubentryData]:
    """Build subentry data for manually configured device IPs."""
    return [
        ConfigSubentryData(
            data={CONF_DEVICE_IP: ip},
            subentry_type=SUBENTRY_TYPE_DEVICE,
            title=ip,
            unique_id=ip,
        )
        for ip in ips
    ]


async def _async_reconfigure_subentry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    new_ip: str,
    subentry_id: str | None = None,
) -> SubentryFlowResult:
    """Run the reconfigure flow of a device subentry, the entry's only one by default."""
    if subentry_id is None:
        subentry_id = next(iter(config_entry.subentries))
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_DEVICE),
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "subentry_id": subentry_id,
        },
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DEVICE_IP: new_ip}
    )
    await hass.async_block_till_done()
    return result


async def _async_setup_manual_device(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> tuple[MockConfigEntry, GoveeDevice]:
    """Set up an entry with one answered manual lamp at 192.168.1.100."""
    manual_device = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.100",
        fingerprint="manual_device-fingerprint",
        sku="H615A",
        capabilities=DEFAULT_CAPABILITIES,
    )
    manual_device.is_manual = True
    set_mocked_devices(mock_govee_api, [manual_device])

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        subentries_data=_device_subentries(manual_device.ip),
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry, manual_device


async def _async_setup_two_manual_devices(
    hass: HomeAssistant, mock_govee_api: AsyncMock, freezer: FrozenDateTimeFactory
) -> tuple[MockConfigEntry, GoveeDevice, GoveeDevice]:
    """Set up an entry with two answered manual lamps at 192.168.1.100 and .101."""
    device_a = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.100",
        fingerprint="manual_device-fingerprint",
        sku="H615A",
        capabilities=DEFAULT_CAPABILITIES,
    )
    device_a.is_manual = True
    device_b = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.101",
        fingerprint="other-fingerprint",
        sku="H615B",
        capabilities=DEFAULT_CAPABILITIES,
    )
    device_b.is_manual = True
    set_mocked_devices(mock_govee_api, [device_a, device_b])

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        subentries_data=_device_subentries(device_a.ip, device_b.ip),
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # The lamps answered the probes queued at startup; a poll lets the sweep
    # acknowledge that, since the mocked library cannot drain the queue.
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert config_entry.runtime_data.discovery_queue == set()

    return config_entry, device_a, device_b


def _subentry_id_of(config_entry: MockConfigEntry, unique_id: str) -> str:
    """Return the id of the device subentry with this unique id."""
    return next(
        subentry.subentry_id
        for subentry in config_entry.subentries.values()
        if subentry.unique_id == unique_id
    )


async def test_setup_entry_with_manual_devices(
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
        subentries_data=_device_subentries("192.168.1.100"),
    )

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_govee_api.add_device_to_discovery_queue.assert_called_once_with(
        "192.168.1.100"
    )


async def test_remove_subentry_removes_discovered_device(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a discovered manual device is removed with its subentry."""

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
        subentries_data=_device_subentries(manual_device1.ip, manual_device2.ip),
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is config_entries.ConfigEntryState.LOADED
    assert entity_registry.async_get("light.h615a") is not None
    assert entity_registry.async_get("light.h615b") is not None

    # Deleting the subentry is the whole removal instruction.
    subentry = next(
        sub
        for sub in config_entry.subentries.values()
        if sub.unique_id == manual_device1.ip
    )
    hass.config_entries.async_remove_subentry(config_entry, subentry.subentry_id)
    await hass.async_block_till_done()

    assert config_entry.state is config_entries.ConfigEntryState.LOADED
    mock_govee_api.remove_device.assert_called_once_with(manual_device1)
    assert {sub.unique_id for sub in config_entry.subentries.values()} == {
        manual_device2.ip
    }
    assert entity_registry.async_get("light.h615b") is not None
    assert entity_registry.async_get("light.h615a") is None


async def test_remove_multiple_subentries(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test removing several devices in quick succession.

    The listener has to cope with more than one device disappearing at once.
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
        subentries_data=_device_subentries(*(device.ip for device in devices)),
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get("light.h615a") is not None
    assert entity_registry.async_get("light.h615b") is not None

    for subentry_id in list(config_entry.subentries):
        hass.config_entries.async_remove_subentry(config_entry, subentry_id)
    await hass.async_block_till_done()

    assert config_entry.state is config_entries.ConfigEntryState.LOADED
    assert mock_govee_api.remove_device.call_count == 2
    assert config_entry.subentries == {}
    assert entity_registry.async_get("light.h615a") is None
    assert entity_registry.async_get("light.h615b") is None


async def test_remove_subentry_device_in_queue(
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
        subentries_data=_device_subentries(manual_device1.ip),
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Queue an IP that never answers, then drop it again.
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_DEVICE),
        context={"source": config_entries.SOURCE_USER},
    )
    await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DEVICE_IP: "192.168.1.101"}
    )
    await hass.async_block_till_done()
    assert "192.168.1.101" in mock_govee_api.discovery_queue

    subentry = next(
        sub
        for sub in config_entry.subentries.values()
        if sub.unique_id == "192.168.1.101"
    )
    hass.config_entries.async_remove_subentry(config_entry, subentry.subentry_id)
    await hass.async_block_till_done()

    assert config_entry.state is config_entries.ConfigEntryState.LOADED
    assert "192.168.1.101" not in mock_govee_api.discovery_queue
    # The already-discovered device is untouched.
    assert len(hass.states.async_all()) == 1


async def test_add_subentry_queues_device(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test adding a device subentry queues its IP for discovery."""

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

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_DEVICE),
        context={"source": config_entries.SOURCE_USER},
    )
    await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DEVICE_IP: "192.168.1.100"}
    )
    await hass.async_block_till_done()

    mock_govee_api.add_device_to_discovery_queue.assert_called_once_with(
        "192.168.1.100"
    )


async def test_reconfigure_preserves_registry_entries(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test reconfiguring a device's IP keeps its registry entries and customizations."""

    config_entry, manual_device = await _async_setup_manual_device(hass, mock_govee_api)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, manual_device.fingerprint), config_entry.entry_id
    )
    assert device_entry is not None
    entity_registry.async_update_entity("light.h615a", name="Living room lamp")

    result = await _async_reconfigure_subentry(hass, config_entry, "192.168.1.102")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    # The lamp keeps its identity: it is only expected at a new address.
    mock_govee_api.remove_device.assert_not_called()
    preserved_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, manual_device.fingerprint), config_entry.entry_id
    )
    assert preserved_device is not None
    assert preserved_device.id == device_entry.id
    entity_entry = entity_registry.async_get("light.h615a")
    assert entity_entry is not None
    assert entity_entry.name == "Living room lamp"
    # The new address is probed.
    mock_govee_api.add_device_to_discovery_queue.assert_called_with("192.168.1.102")


async def test_reconfigure_entity_id_not_claimed_by_other_lamp(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test another same-model lamp cannot claim a reconfigured lamp's entity ID."""

    config_entry, manual_device = await _async_setup_manual_device(hass, mock_govee_api)

    await _async_reconfigure_subentry(hass, config_entry, "192.168.1.102")

    # A second lamp of the same model is discovered before the reconfigured
    # one answers at its new address.
    other_device = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.50",
        fingerprint="other-fingerprint",
        sku="H615A",
        capabilities=DEFAULT_CAPABILITIES,
    )
    set_mocked_devices(mock_govee_api, [manual_device, other_device])
    discovery_callback = mock_govee_api.set_device_discovered_callback.call_args[0][0]
    discovery_callback(other_device, True)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get("light.h615a")
    assert entity_entry is not None
    assert entity_entry.unique_id == manual_device.fingerprint
    other_entry = entity_registry.async_get("light.h615a_2")
    assert other_entry is not None
    assert other_entry.unique_id == other_device.fingerprint


async def test_reconfigured_device_answers_at_new_ip(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a lamp answering at its new address keeps its entity and drains the queue."""

    config_entry, manual_device = await _async_setup_manual_device(hass, mock_govee_api)

    await _async_reconfigure_subentry(hass, config_entry, "192.168.1.102")

    coordinator = config_entry.runtime_data
    assert coordinator.discovery_queue == {"192.168.1.102"}

    # A known lamp answering from the probed address keeps its device object:
    # the library updates its IP in place and reports it as not new.
    manual_device.update_ip("192.168.1.102")
    discovery_callback = mock_govee_api.set_device_discovered_callback.call_args[0][0]
    discovery_callback(manual_device, False)
    await hass.async_block_till_done()

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert entity_registry.async_get("light.h615a") is not None
    assert hass.states.get("light.h615a") is not None
    assert coordinator.discovery_queue == set()
    # Draining the probe must not make the controller forget the lamp.
    assert coordinator.devices == [manual_device]
    assert manual_device.is_manual is True


async def _async_setup_manual_and_discovered(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> tuple[MockConfigEntry, GoveeDevice, GoveeDevice]:
    """Set up a manual lamp at 192.168.1.100 and a discovered one at .50."""
    manual_device = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.100",
        fingerprint="manual_device-fingerprint",
        sku="H615A",
        capabilities=DEFAULT_CAPABILITIES,
    )
    manual_device.is_manual = True
    other_device = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.50",
        fingerprint="other-fingerprint",
        sku="H615B",
        capabilities=DEFAULT_CAPABILITIES,
    )
    set_mocked_devices(mock_govee_api, [manual_device, other_device])

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        subentries_data=_device_subentries(manual_device.ip),
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry, manual_device, other_device


async def test_reconfigure_to_discovered_lamp_ip_does_not_adopt(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test reconfiguring to a discovered lamp's IP leaves that lamp alone.

    The controller's IP map may be stale after a DHCP reshuffle, so the new
    address cannot be rejected up front. Adopting the other lamp instead would
    put two lamps under one subentry, making either deletion cascade to both.
    """

    (
        config_entry,
        manual_device,
        other_device,
    ) = await _async_setup_manual_and_discovered(hass, mock_govee_api)
    subentry_id = next(iter(config_entry.subentries))

    result = await _async_reconfigure_subentry(hass, config_entry, other_device.ip)
    assert result["reason"] == "reconfigure_successful"

    # The configured address is still probed for the subentry's own lamp: the
    # cached device at that address may be stale.
    assert config_entry.runtime_data.discovery_queue == {other_device.ip}

    # The discovered lamp stays on the main entry, unclaimed.
    other_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, other_device.fingerprint), config_entry.entry_id
    )
    assert other_entry is not None
    assert other_entry.config_subentry_id is None
    assert other_device.is_manual is False
    # The subentry stays bound to its original lamp.
    manual_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, manual_device.fingerprint), config_entry.entry_id
    )
    assert manual_entry is not None
    assert manual_entry.config_subentry_id == subentry_id

    # Deleting the subentry only cascades to its own lamp: the unclaimed lamp
    # at the still-probed address must survive, and the probe is dropped.
    hass.config_entries.async_remove_subentry(config_entry, subentry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get("light.h615a") is None
    assert entity_registry.async_get("light.h615b") is not None
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, other_device.fingerprint), config_entry.entry_id
        )
        is not None
    )
    mock_govee_api.remove_device.assert_called_once_with(manual_device)
    assert config_entry.runtime_data.discovery_queue == set()


async def test_poll_keeps_probe_for_unanswered_reconfigured_address(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a stale device at a reconfigured address does not cancel its probe."""

    config_entry, _, other_device = await _async_setup_manual_and_discovered(
        hass, mock_govee_api
    )

    await _async_reconfigure_subentry(hass, config_entry, other_device.ip)

    coordinator = config_entry.runtime_data
    assert coordinator.discovery_queue == {other_device.ip}

    # The cached device at the address has not answered the probe, so the
    # probe must keep running.
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.discovery_queue == {other_device.ip}


async def test_reconfigured_lamp_recovers_at_other_lamps_stale_address(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the subentry's lamp is recovered at an address with a stale tenant."""

    (
        config_entry,
        manual_device,
        other_device,
    ) = await _async_setup_manual_and_discovered(hass, mock_govee_api)
    subentry_id = next(iter(config_entry.subentries))

    await _async_reconfigure_subentry(hass, config_entry, other_device.ip)

    # Without this probe the lamp could never answer at the new address.
    assert config_entry.runtime_data.discovery_queue == {other_device.ip}

    # The stale tenant never answers and gets evicted; the subentry's own lamp
    # answers the probe, so the library updates its address in place.
    manual_device.update_ip(other_device.ip)
    set_mocked_devices(mock_govee_api, [manual_device])
    discovery_callback = mock_govee_api.set_device_discovered_callback.call_args[0][0]
    discovery_callback(manual_device, False)
    await hass.async_block_till_done()

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get("light.h615a")
    assert entity_entry is not None
    assert entity_entry.unique_id == manual_device.fingerprint
    manual_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, manual_device.fingerprint), config_entry.entry_id
    )
    assert manual_entry is not None
    assert manual_entry.config_subentry_id == subentry_id
    assert config_entry.runtime_data.discovery_queue == set()


async def test_unknown_lamp_at_reconfigured_address_stays_unclaimed(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an unknown lamp answering at a reconfigured address is not claimed.

    The subentry still owns its original lamp, so the answering lamp must stay
    an ordinary discovered device on the main entry and the probe must keep
    waiting for the owner.
    """

    config_entry, manual_device = await _async_setup_manual_device(hass, mock_govee_api)
    subentry_id = next(iter(config_entry.subentries))

    await _async_reconfigure_subentry(hass, config_entry, "192.168.1.50")

    coordinator = config_entry.runtime_data
    assert coordinator.discovery_queue == {"192.168.1.50"}

    # A lamp with an unknown fingerprint answers the probe. The library drains
    # the queue entry, marks the lamp manual and reports it as new.
    other_device = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.50",
        fingerprint="other-fingerprint",
        sku="H615B",
        capabilities=DEFAULT_CAPABILITIES,
    )
    other_device.is_manual = True
    mock_govee_api.remove_device_from_discovery_queue("192.168.1.50")
    set_mocked_devices(mock_govee_api, [manual_device, other_device])
    discovery_callback = mock_govee_api.set_device_discovered_callback.call_args[0][0]
    discovery_callback(other_device, True)
    await hass.async_block_till_done()

    # The answering lamp is a plain discovered device on the main entry.
    other_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, other_device.fingerprint), config_entry.entry_id
    )
    assert other_entry is not None
    assert other_entry.config_subentry_id is None
    assert other_device.is_manual is False
    assert entity_registry.async_get("light.h615b") is not None
    # The subentry still belongs to its original lamp, and the probe for it
    # keeps running.
    manual_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, manual_device.fingerprint), config_entry.entry_id
    )
    assert manual_entry is not None
    assert manual_entry.config_subentry_id == subentry_id
    assert entity_registry.async_get("light.h615a") is not None
    # The next poll restores the probe the library consumed for the wrong lamp.
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert coordinator.discovery_queue == {"192.168.1.50"}

    # Deleting the subentry only cascades to its own lamp.
    hass.config_entries.async_remove_subentry(config_entry, subentry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get("light.h615a") is None
    assert entity_registry.async_get("light.h615b") is not None
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, other_device.fingerprint), config_entry.entry_id
        )
        is not None
    )
    mock_govee_api.remove_device.assert_called_once_with(manual_device)
    assert coordinator.discovery_queue == set()


async def test_probe_queued_when_other_manual_lamp_caches_address(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a probe is queued although another manual lamp is cached at the address."""

    config_entry, device_a, device_b = await _async_setup_two_manual_devices(
        hass, mock_govee_api, freezer
    )
    subentry_a = _subentry_id_of(config_entry, device_a.ip)
    subentry_b = _subentry_id_of(config_entry, device_b.ip)

    # B is expected at a new address but still answers at the old one; A is
    # then expected at B's cached address.
    await _async_reconfigure_subentry(hass, config_entry, "192.168.1.103", subentry_b)
    await _async_reconfigure_subentry(hass, config_entry, "192.168.1.101", subentry_a)

    coordinator = config_entry.runtime_data
    assert coordinator.discovery_queue == {"192.168.1.101", "192.168.1.103"}
    # The cached lamp is untouched: still manual, still owning its subentry.
    assert device_b.is_manual is True
    entry_b = device_registry.async_get_device_by_identifier(
        (DOMAIN, device_b.fingerprint), config_entry.entry_id
    )
    assert entry_b is not None
    assert entry_b.config_subentry_id == subentry_b
    entry_a = device_registry.async_get_device_by_identifier(
        (DOMAIN, device_a.fingerprint), config_entry.entry_id
    )
    assert entry_a is not None
    assert entry_a.config_subentry_id == subentry_a


async def test_lamp_keeps_subentry_association_across_restart(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a lamp answering at its old address keeps its subentry after a restart."""

    device = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.100",
        fingerprint="manual_device-fingerprint",
        sku="H615A",
        capabilities=DEFAULT_CAPABILITIES,
    )
    set_mocked_devices(mock_govee_api, [device])

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        subentries_data=_device_subentries("192.168.1.102"),
    )
    config_entry.add_to_hass(hass)
    subentry_id = next(iter(config_entry.subentries))
    # The previous session stored the lamp under its subentry.
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        config_subentry_id=subentry_id,
        identifiers={(DOMAIN, device.fingerprint)},
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # The lamp answered at its old address: the stored association wins over
    # the address mismatch.
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, device.fingerprint), config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry.config_subentry_id == subentry_id
    assert device.is_manual is True
    assert entity_registry.async_get("light.h615a") is not None

    # The probe at the reconfigured address keeps waiting for the lamp.
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert config_entry.runtime_data.discovery_queue == {"192.168.1.102"}

    # Deleting the subentry removes the lamp wherever it answered.
    hass.config_entries.async_remove_subentry(config_entry, subentry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get("light.h615a") is None
    mock_govee_api.remove_device.assert_called_once_with(device)
    assert config_entry.runtime_data.discovery_queue == set()


async def test_probe_not_drained_by_other_subentrys_lamp(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test another subentry's lamp answering at a probed address keeps the probe."""

    config_entry, device_a, device_b = await _async_setup_two_manual_devices(
        hass, mock_govee_api, freezer
    )
    subentry_a = _subentry_id_of(config_entry, device_a.ip)
    subentry_b = _subentry_id_of(config_entry, device_b.ip)

    await _async_reconfigure_subentry(hass, config_entry, "192.168.1.102", subentry_a)

    coordinator = config_entry.runtime_data
    assert coordinator.discovery_queue == {"192.168.1.102"}

    # The other subentry's lamp moves to the probed address and answers there.
    device_b.update_ip("192.168.1.102")
    discovery_callback = mock_govee_api.set_device_discovered_callback.call_args[0][0]
    discovery_callback(device_b, False)
    await hass.async_block_till_done()

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # The answer did not come from this subentry's lamp, so its probe stays;
    # the other lamp's configured address, no longer answered, is probed too.
    assert coordinator.discovery_queue == {"192.168.1.101", "192.168.1.102"}
    assert device_b.is_manual is True
    entry_b = device_registry.async_get_device_by_identifier(
        (DOMAIN, device_b.fingerprint), config_entry.entry_id
    )
    assert entry_b is not None
    assert entry_b.config_subentry_id == subentry_b

    # Deleting the waiting subentry drops its probe and only its own lamp; the
    # other lamp is then probed at its own configured address again.
    hass.config_entries.async_remove_subentry(config_entry, subentry_a)
    await hass.async_block_till_done()

    assert entity_registry.async_get("light.h615a") is None
    assert entity_registry.async_get("light.h615b") is not None
    mock_govee_api.remove_device.assert_called_once_with(device_a)
    assert coordinator.discovery_queue == {"192.168.1.101"}


async def test_probe_restored_when_new_reply_is_other_subentrys_lamp(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a probe consumed by another subentry's lamp is restored.

    After a restart a lamp can own its subentry in the registry while being
    new to the controller. Answering another subentry's probe makes the
    library consume that probe for it, so the claim has to restore it.
    """

    # Setup waits for discovery to find a device, so seed one that answered.
    discovered = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.50",
        fingerprint="discovered-fingerprint",
        sku="H615C",
        capabilities=DEFAULT_CAPABILITIES,
    )
    set_mocked_devices(mock_govee_api, [discovered])

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        subentries_data=_device_subentries("192.168.1.100", "192.168.1.101"),
    )
    config_entry.add_to_hass(hass)
    subentry_b = _subentry_id_of(config_entry, "192.168.1.101")
    # The previous session stored the second lamp under its subentry.
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        config_subentry_id=subentry_b,
        identifiers={(DOMAIN, "other-fingerprint")},
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data
    assert coordinator.discovery_queue == {"192.168.1.100", "192.168.1.101"}

    # The second lamp answers the first subentry's probe: the library drains
    # that probe, marks the lamp manual and reports it as new.
    other_device = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.100",
        fingerprint="other-fingerprint",
        sku="H615B",
        capabilities=DEFAULT_CAPABILITIES,
    )
    other_device.is_manual = True
    mock_govee_api.remove_device_from_discovery_queue("192.168.1.100")
    set_mocked_devices(mock_govee_api, [discovered, other_device])
    discovery_callback = mock_govee_api.set_device_discovered_callback.call_args[0][0]
    discovery_callback(other_device, True)
    await hass.async_block_till_done()

    # The lamp keeps its own subentry, and the consumed probe is restored.
    entry_b = device_registry.async_get_device_by_identifier(
        (DOMAIN, other_device.fingerprint), config_entry.entry_id
    )
    assert entry_b is not None
    assert entry_b.config_subentry_id == subentry_b
    assert other_device.is_manual is True
    # The next poll restores the probe the library consumed for this lamp.
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert coordinator.discovery_queue == {"192.168.1.100", "192.168.1.101"}


async def test_poll_prunes_probe_without_subentry(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a probe at an address no subentry is configured with is pruned.

    Evicting a lamp kept through a reconfigure re-queues its old cached
    address, which nothing can complete.
    """

    config_entry, manual_device = await _async_setup_manual_device(hass, mock_govee_api)

    await _async_reconfigure_subentry(hass, config_entry, "192.168.1.102")

    coordinator = config_entry.runtime_data
    assert coordinator.discovery_queue == {"192.168.1.102"}

    # The kept lamp never answers: the library evicts it and re-queues its
    # old cached address.
    set_mocked_devices(mock_govee_api, [])
    mock_govee_api.add_device_to_discovery_queue(manual_device.ip)

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.discovery_queue == {"192.168.1.102"}


async def test_known_lamp_adopted_when_answering_at_added_address(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a known lamp answering a fresh subentry's probe is adopted."""

    device = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.50",
        fingerprint="discovered-fingerprint",
        sku="H615B",
        capabilities=DEFAULT_CAPABILITIES,
    )
    set_mocked_devices(mock_govee_api, [device])

    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # The lamp moved to a new address; the user adds it manually there.
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_DEVICE),
        context={"source": config_entries.SOURCE_USER},
    )
    await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DEVICE_IP: "192.168.1.60"}
    )
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data
    assert coordinator.discovery_queue == {"192.168.1.60"}
    subentry_id = next(iter(config_entry.subentries))

    # The lamp answers the probe: known fingerprint, address updated in place.
    device.update_ip("192.168.1.60")
    discovery_callback = mock_govee_api.set_device_discovered_callback.call_args[0][0]
    discovery_callback(device, False)
    await hass.async_block_till_done()

    # The next poll adopts the known lamp and completes the probe.
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert device.is_manual is True
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, device.fingerprint), config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry.config_subentry_id == subentry_id
    # The existing entity moved with the device; no duplicate was created.
    entity_entry = entity_registry.async_get("light.h615b")
    assert entity_entry is not None
    assert entity_entry.config_subentry_id == subentry_id
    assert entity_registry.async_get("light.h615b_2") is None
    assert coordinator.discovery_queue == set()
    # Draining the probe must not make the controller forget the lamp.
    assert coordinator.devices == [device]


async def test_stale_cached_lamp_not_adopted_at_added_address(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a lamp only cached at an added address is not adopted there."""

    stale = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.50",
        fingerprint="stale-fingerprint",
        sku="H615B",
        capabilities=DEFAULT_CAPABILITIES,
    )
    set_mocked_devices(mock_govee_api, [stale])

    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # The cached lamp is gone and its address now belongs to another lamp,
    # which the user adds manually.
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_DEVICE),
        context={"source": config_entries.SOURCE_USER},
    )
    await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DEVICE_IP: "192.168.1.50"}
    )
    await hass.async_block_till_done()

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data
    subentry_id = next(iter(config_entry.subentries))

    # Without a scan reply the cache is no evidence of who is at the address.
    assert stale.is_manual is False
    stale_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, stale.fingerprint), config_entry.entry_id
    )
    assert stale_entry is not None
    assert stale_entry.config_subentry_id is None
    assert coordinator.discovery_queue == {"192.168.1.50"}

    # The lamp really at the address answers the probe.
    current = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.50",
        fingerprint="current-fingerprint",
        sku="H615A",
        capabilities=DEFAULT_CAPABILITIES,
    )
    # The library marks whatever answers a queued probe.
    current.is_manual = True
    set_mocked_devices(mock_govee_api, [stale, current])
    discovery_callback = mock_govee_api.set_device_discovered_callback.call_args[0][0]
    discovery_callback(current, True)
    await hass.async_block_till_done()

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    current_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, current.fingerprint), config_entry.entry_id
    )
    assert current_entry is not None
    assert current_entry.config_subentry_id == subentry_id
    stale_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, stale.fingerprint), config_entry.entry_id
    )
    assert stale_entry is not None
    assert stale_entry.config_subentry_id is None
    assert coordinator.discovery_queue == set()


async def test_reconfigure_queued_device(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test reconfiguring a lamp that never answered swaps the probed address."""

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
        subentries_data=_device_subentries("192.168.1.100"),
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data
    assert coordinator.discovery_queue == {"192.168.1.100"}

    result = await _async_reconfigure_subentry(hass, config_entry, "192.168.1.102")

    assert result["reason"] == "reconfigure_successful"
    assert coordinator.discovery_queue == {"192.168.1.102"}


async def test_subentry_added_during_setup_is_queued(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test a device added while setup is still starting up reaches the controller."""

    discovered = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.50",
        fingerprint="discovered-fingerprint",
        sku="H615B",
        capabilities=DEFAULT_CAPABILITIES,
    )
    set_mocked_devices(mock_govee_api, [discovered])

    start_blocked = asyncio.Event()

    async def _start(**kwargs: bool) -> None:
        await start_blocked.wait()

    mock_govee_api.start.side_effect = _start

    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)

    setup_task = hass.async_create_task(
        hass.config_entries.async_setup(config_entry.entry_id)
    )
    await asyncio.sleep(0)
    assert not setup_task.done()

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_DEVICE),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DEVICE_IP: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    # Setup is still parked in start(), so only yield to let the update
    # listener run; waiting for all tasks would deadlock on the setup task.
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    mock_govee_api.add_device_to_discovery_queue.assert_called_once_with(
        "192.168.1.100"
    )

    start_blocked.set()
    assert await setup_task
    await hass.async_block_till_done()

    assert config_entry.state is config_entries.ConfigEntryState.LOADED


async def test_add_subentry_adopts_discovered_device(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test adding a subentry for an already-discovered lamp claims it.

    Once it answers the probe, the lamp must become manual and its
    registrations must move under the subentry, so deleting the subentry later
    cascades to them.
    """
    discovered = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.100",
        fingerprint="discovered-fingerprint",
        sku="H615A",
        capabilities=DEFAULT_CAPABILITIES,
    )
    set_mocked_devices(mock_govee_api, [discovered])

    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_DEVICE),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DEVICE_IP: discovered.ip}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    subentry_id = next(iter(config_entry.subentries))
    # The cached address alone is not trusted, so the lamp is probed.
    assert config_entry.runtime_data.discovery_queue == {discovered.ip}
    assert discovered.is_manual is False

    # The lamp answers the probe: known fingerprint at the configured address.
    discovery_callback = mock_govee_api.set_device_discovered_callback.call_args[0][0]
    discovery_callback(discovered, False)
    await hass.async_block_till_done()

    assert discovered.is_manual is True
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, discovered.fingerprint), config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry.config_subentry_id == subentry_id
    entity = entity_registry.async_get("light.h615a")
    assert entity is not None
    assert entity.config_subentry_id == subentry_id
    assert hass.states.get("light.H615A") is not None

    # Deleting the subentry now cascades to the adopted registrations.
    hass.config_entries.async_remove_subentry(config_entry, subentry_id)
    await hass.async_block_till_done()

    assert hass.states.get("light.H615A") is None
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, discovered.fingerprint), config_entry.entry_id
        )
        is None
    )
    mock_govee_api.remove_device.assert_called_once_with(discovered)


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
            id="discovered_device_leaves_subentries_alone",
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
    configured, so a configured device also loses its subentry (otherwise the
    reconcile would re-add it), while a purely discovered one leaves the
    subentries untouched.
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
        subentries_data=_device_subentries(*initial_manual_devices),
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
    assert {subentry.unique_id for subentry in config_entry.subentries.values()} == set(
        expected_manual_devices
    )
    # The other device is left alone either way.
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, other.fingerprint), config_entry.entry_id
        )
        is not None
    )
    assert mock_govee_api.get_device_by_fingerprint(device.fingerprint) is None


async def test_remove_queued_device_from_device_page(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_govee_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test deleting a configured device that has not answered since startup.

    Its registry entry persists from an earlier session, but the controller
    only has the IP in its discovery queue, so the removal must be resolved
    from the device's subentry link rather than from the controller.
    """
    assert await async_setup_component(hass, "config", {})

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
        subentries_data=_device_subentries("192.168.1.100"),
    )
    config_entry.add_to_hass(hass)
    subentry_id = next(iter(config_entry.subentries))

    # The device registry entry left behind by an earlier session.
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        config_subentry_id=subentry_id,
        identifiers={(DOMAIN, "manual-fingerprint")},
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert "192.168.1.100" in mock_govee_api.discovery_queue

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "config/device_registry/remove", "device_id": device_entry.id}
    )
    response = await client.receive_json()
    await hass.async_block_till_done()

    assert response["success"]
    assert config_entry.subentries == {}
    assert "192.168.1.100" not in mock_govee_api.discovery_queue
    assert device_registry.async_get(device_entry.id) is None


async def test_remove_device_when_entry_not_loaded(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_govee_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test deleting a manual device while the entry is unloaded drops its subentry."""
    assert await async_setup_component(hass, "config", {})

    manual_device = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.100",
        fingerprint="manual-fingerprint",
        sku="H615A",
        capabilities=DEFAULT_CAPABILITIES,
    )
    manual_device.is_manual = True
    set_mocked_devices(mock_govee_api, [manual_device])

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        subentries_data=_device_subentries(manual_device.ip),
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, manual_device.fingerprint), config_entry.entry_id
    )
    assert device_entry is not None

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is config_entries.ConfigEntryState.NOT_LOADED

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "config/device_registry/remove", "device_id": device_entry.id}
    )
    response = await client.receive_json()
    await hass.async_block_till_done()

    assert response["success"]
    assert config_entry.subentries == {}
    assert device_registry.async_get(device_entry.id) is None


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
    """Test a removal belonging to another entry leaves our subentries alone."""
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
        subentries_data=_device_subentries("192.168.1.100"),
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

    assert {sub.unique_id for sub in config_entry.subentries.values()} == {
        "192.168.1.100"
    }
