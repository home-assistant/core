"""Multi-server lifecycle and isolated recovery for ordinary coordinators."""

import asyncio
from collections.abc import Callable
from dataclasses import replace
from unittest.mock import AsyncMock, Mock, patch

from lorawan_connection import (
    ConnectionUnavailable,
    DeviceEvent,
    Downlink,
    DownlinkError,
    EventType,
    UplinkEvent,
)
import pytest

from homeassistant.components.lorawan import DeviceManager, async_get_connections
from homeassistant.components.lorawan.connection import RegisteredConnection
from homeassistant.components.lorawan.device_manager import _CollectionConnection
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import RegisterBackend
from .helpers import DESCRIPTOR, ExampleCoordinator, ExampleDevices, inventory

from tests.common import MockConfigEntry


async def test_multiple_connections_reconnect(
    hass: HomeAssistant,
    registered_backend: RegisterBackend,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Same EUI on two connections stays independent; reconnect reuses coordinators."""
    first, unregister = await registered_backend("network", [DESCRIPTOR])
    other = replace(DESCRIPTOR, network_id="other", name="Bedroom")
    _second, _ = await registered_backend("other", [other])
    entry = MockConfigEntry(domain="test_vendor")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = entry.runtime_data
    coordinator = manager.coordinators[("network", DESCRIPTOR.dev_eui)]
    model = coordinator.data
    assert len(manager.coordinators) == 2
    assert len(dr.async_entries_for_config_entry(device_registry, entry.entry_id)) == 2
    before = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        first.disconnect()
        await hass.async_block_till_done()
    reload.assert_not_called()
    assert hass.states.get("sensor.greenhouse_temperature").state == "unavailable"
    assert hass.states.get("sensor.bedroom_temperature").state == "unknown"
    assert entry.state is ConfigEntryState.LOADED
    assert not model.closed
    assert "network" not in async_get_connections(hass)
    unregister()
    first, _ = await registered_backend("network", [DESCRIPTOR])
    await hass.async_block_till_done()
    assert manager.coordinators[("network", DESCRIPTOR.dev_eui)] is coordinator
    assert coordinator.data is model
    assert hass.states.get("sensor.greenhouse_temperature").state == "unknown"
    assert er.async_entries_for_config_entry(entity_registry, entry.entry_id) == before
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert model.closed


async def test_late_connections(
    hass: HomeAssistant, registered_backend: RegisterBackend
) -> None:
    """A vendor starts without servers and consumes future registrations."""
    entry = MockConfigEntry(domain="test_vendor")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert not entry.runtime_data.coordinators
    await registered_backend("network", [DESCRIPTOR])
    await hass.async_block_till_done()
    assert hass.states.get("sensor.greenhouse_temperature") is not None
    assert len(entry.runtime_data.coordinators) == 1
    await hass.config_entries.async_unload(entry.entry_id)


async def test_offline_removals(
    hass: HomeAssistant,
    registered_backend: RegisterBackend,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Reconnect removes missing devices only from that connection."""
    _, unregister = await registered_backend("network", [DESCRIPTOR])
    other = replace(DESCRIPTOR, network_id="other", name="Bedroom")
    await registered_backend("other", [other])
    entry = MockConfigEntry(domain="test_vendor")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    unregister()
    assert len(dr.async_entries_for_config_entry(device_registry, entry.entry_id)) == 2
    await registered_backend("network", [])
    await hass.async_block_till_done()
    assert hass.states.get("sensor.greenhouse_temperature") is None
    assert hass.states.get("sensor.bedroom_temperature") is not None
    assert len(dr.async_entries_for_config_entry(device_registry, entry.entry_id)) == 1
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 2
    await hass.config_entries.async_unload(entry.entry_id)


async def test_deleted_server(
    hass: HomeAssistant,
    registered_backend: RegisterBackend,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Deleting a config entry cleans up its devices even after disconnect."""
    _, unregister = await registered_backend("network", [DESCRIPTOR])
    entry = MockConfigEntry(domain="test_vendor")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    unregister()
    await hass.config_entries.async_remove("network")
    await hass.async_block_till_done()
    assert not dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert not entry.runtime_data.coordinators
    assert hass.states.get("sensor.greenhouse_temperature") is None
    await hass.config_entries.async_unload(entry.entry_id)


async def test_startup_cleanup(
    hass: HomeAssistant,
    registered_backend: RegisterBackend,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Startup keeps offline-server devices and removes records for deleted servers."""
    await registered_backend("network", [])
    MockConfigEntry(domain="test_provider", entry_id="offline").add_to_hass(hass)
    entry = MockConfigEntry(domain="test_vendor")
    entry.add_to_hass(hass)
    missing = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("test_vendor", "deleted:0000000000000001")},
    )
    stale = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("test_vendor", "network:0000000000000001")},
    )
    offline = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("test_vendor", "offline:0000000000000001")},
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert device_registry.async_get(missing.id) is None
    assert device_registry.async_get(stale.id) is None
    assert device_registry.async_get(offline.id) is not None
    await hass.config_entries.async_unload(entry.entry_id)


async def test_coordinator_listener_cleanup(
    hass: HomeAssistant, registered_backend: RegisterBackend
) -> None:
    """Subscriptions replay ready coordinators and unsubscribe independently."""
    backend, _ = await registered_backend("network", [DESCRIPTOR])
    entry = MockConfigEntry(domain="test_vendor")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    delivered = []
    unsubscribe = entry.runtime_data.subscribe_coordinator_added(delivered.append)
    assert delivered[0].data.descriptor == DESCRIPTOR
    unsubscribe()
    unsubscribe()
    backend.emit(inventory(replace(DESCRIPTOR, dev_eui="0201010101010102")))
    assert len(delivered) == 1
    manager = entry.runtime_data
    await hass.config_entries.async_unload(entry.entry_id)
    with pytest.raises(RuntimeError, match="closed"):
        manager.subscribe_coordinator_added(delivered.append)


async def test_reconnect_routes_commands_to_new_transport(
    hass: HomeAssistant, registered_backend: RegisterBackend
) -> None:
    """A retained model sends subsequent commands through the replacement backend."""

    first, unregister = await registered_backend("network", [DESCRIPTOR])
    entry = MockConfigEntry(domain="test_vendor")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    device = entry.runtime_data.coordinators[("network", DESCRIPTOR.dev_eui)].data
    with patch.object(
        first, "async_send_downlink", new=AsyncMock(return_value="one")
    ) as send:
        await device.async_send_downlink(data=b"first", f_port=2, wait_for_ack=False)
        send.assert_awaited_once()
        unregister()
        second, _ = await registered_backend("network", [DESCRIPTOR])
        await hass.async_block_till_done()
        with patch.object(
            second, "async_send_downlink", new=AsyncMock(return_value="two")
        ) as replacement:
            await device.async_send_downlink(
                data=b"second", f_port=2, wait_for_ack=False
            )
            replacement.assert_awaited_once()
        send.assert_awaited_once()
    await hass.config_entries.async_unload(entry.entry_id)


async def test_pending_command_fails_on_disconnect(
    hass: HomeAssistant, registered_backend: RegisterBackend
) -> None:
    """Disconnect fails ACK waits while preserving models and entity registrations."""

    backend, unregister = await registered_backend("network", [DESCRIPTOR])
    entry = MockConfigEntry(domain="test_vendor")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    device = entry.runtime_data.coordinators[("network", DESCRIPTOR.dev_eui)].data
    with patch.object(
        backend, "async_send_downlink", new=AsyncMock(return_value="one")
    ):
        command = hass.async_create_task(
            device.async_send_downlink(data=b"command", f_port=2)
        )
        await asyncio.sleep(0)
        unregister()
        with pytest.raises(DownlinkError, match="Connection was lost"):
            await command
    assert not device.closed
    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    "error", [RuntimeError("setup failed"), asyncio.CancelledError()]
)
async def test_collection_setup_failure_cleanup(
    hass: HomeAssistant, registered_backend: RegisterBackend, error: BaseException
) -> None:
    """Failed or cancelled collection setup releases subscriptions and models."""

    await registered_backend("network", [DESCRIPTOR])
    entry = MockConfigEntry(domain="test_vendor")
    entry.add_to_hass(hass)
    manager = DeviceManager(
        hass,
        entry,
        create_collection=ExampleDevices,
        create_coordinator=ExampleCoordinator,
    )
    with (
        patch.object(ExampleDevices, "async_setup", side_effect=error),
        pytest.raises(type(error)),
    ):
        await manager.async_setup()
    assert not manager.coordinators
    assert not manager._sessions
    manager.close()
    with pytest.raises(RuntimeError, match="closed"):
        await manager.async_setup()


async def test_coordinator_creation_failure(
    hass: HomeAssistant, registered_backend: RegisterBackend
) -> None:
    """A failed coordinator cannot leave a partially loaded vendor integration."""

    await registered_backend("network", [DESCRIPTOR])
    entry = MockConfigEntry(domain="test_vendor")
    entry.add_to_hass(hass)
    manager = DeviceManager(
        hass,
        entry,
        create_collection=ExampleDevices,
        create_coordinator=Mock(side_effect=ValueError("coordinator failed")),
    )
    with pytest.raises(HomeAssistantError, match="coordinator"):
        await manager.async_setup()
    assert not manager.coordinators
    assert not manager._sessions


async def test_listener_replay_failure_unsubscribes(
    hass: HomeAssistant, registered_backend: RegisterBackend
) -> None:
    """An observer that fails during initial replay is not retained."""

    backend, _ = await registered_backend("network", [DESCRIPTOR])
    entry = MockConfigEntry(domain="test_vendor")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    listener = Mock(side_effect=RuntimeError("observer failed"))
    with pytest.raises(RuntimeError, match="observer failed"):
        entry.runtime_data.subscribe_coordinator_added(listener)
    backend.emit(inventory(replace(DESCRIPTOR, dev_eui="0201010101010102")))
    listener.assert_called_once()
    await hass.config_entries.async_unload(entry.entry_id)


async def test_disconnect_during_collection_setup(
    hass: HomeAssistant, registered_backend: RegisterBackend
) -> None:
    """Withdrawal during setup retains the model for a later connection."""

    _, unregister = await registered_backend("network", [DESCRIPTOR])
    entry = MockConfigEntry(domain="test_vendor")
    entry.add_to_hass(hass)
    manager = DeviceManager(
        hass,
        entry,
        create_collection=ExampleDevices,
        create_coordinator=ExampleCoordinator,
    )
    setup = ExampleDevices.async_setup

    async def setup_and_disconnect(collection: ExampleDevices) -> None:
        await setup(collection)
        unregister()

    with patch.object(ExampleDevices, "async_setup", new=setup_and_disconnect):
        await manager.async_setup()
    assert not manager.coordinators[("network", DESCRIPTOR.dev_eui)].last_update_success
    manager.close()
    await hass.async_block_till_done()


async def test_vendor_change_removes_old_model(
    hass: HomeAssistant, registered_backend: RegisterBackend
) -> None:
    """Changing the catalog vendor retires the model without leaking events."""

    backend, _ = await registered_backend("network", [DESCRIPTOR])
    entry = MockConfigEntry(domain="test_vendor")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    backend.emit(inventory(replace(DESCRIPTOR, brand_id=676), EventType.UPDATED))
    await hass.async_block_till_done()
    assert not entry.runtime_data.coordinators
    assert hass.states.get("sensor.greenhouse_temperature") is None
    await hass.config_entries.async_unload(entry.entry_id)


async def test_collection_connection_filter_and_disconnect() -> None:
    """The retained transport filters replay and rejects commands while detached."""

    connection = _CollectionConnection()
    # Ignore activity without a descriptor until inventory identifies the device.
    connection.emit(
        UplinkEvent(
            network_id="network",
            dev_eui=DESCRIPTOR.dev_eui,
            received_at=dt_util.utcnow(),
            data=b"unknown",
        )
    )
    connection.emit(inventory(DESCRIPTOR))
    listener = Mock()
    unsubscribe = await connection.async_subscribe(
        brands=frozenset({("tts", "test_vendor")}), listener=listener
    )
    listener.assert_not_called()
    unsubscribe()
    unsubscribe()
    with pytest.raises(DownlinkError, match="unavailable"):
        await connection.async_send_downlink(
            Downlink(DESCRIPTOR.dev_eui, 1, b"command")
        )


async def test_disconnect_while_vendor_subscribes() -> None:
    """A subscription completing after withdrawal is immediately cleaned up."""

    connection = _CollectionConnection()
    listener = Mock()
    await connection.async_subscribe(brands=None, listener=listener)
    stop_events = Mock()

    async def replay(
        *,
        brands: frozenset[tuple[str, int | str]] | None,
        listener: Callable[[DeviceEvent], None],
    ) -> Mock:
        listener(inventory(DESCRIPTOR))
        connection.detach()
        listener(inventory(replace(DESCRIPTOR, name="Stale"), EventType.UPDATED))
        return stop_events

    backend = Mock(async_subscribe=AsyncMock(side_effect=replay))
    await connection.attach(RegisteredConnection(backend, Mock()))
    stop_events.assert_called_once_with()
    listener.assert_called_once()
    assert connection.registration is None


async def test_vendor_subscription_failure_cleanup(
    hass: HomeAssistant, registered_backend: RegisterBackend
) -> None:
    """A failed vendor replay releases its collection and config-entry listeners."""
    backend, _ = await registered_backend("network", [DESCRIPTOR])
    entry = MockConfigEntry(domain="test_vendor")
    entry.add_to_hass(hass)
    manager = DeviceManager(
        hass,
        entry,
        create_collection=ExampleDevices,
        create_coordinator=ExampleCoordinator,
    )
    with (
        patch.object(backend, "async_subscribe", side_effect=ConnectionUnavailable()),
        pytest.raises(ConnectionUnavailable),
    ):
        await manager.async_setup()
    assert not manager.coordinators
    assert not manager._sessions
    await registered_backend("later", [])
    await hass.async_block_till_done()
    assert not manager._sessions


@pytest.mark.parametrize(
    "method",
    [
        "tests.components.lorawan.helpers.ExampleDevices.async_setup",
        "homeassistant.components.lorawan.device_manager._CollectionConnection.attach",
    ],
    ids=["collection_setup", "subscription"],
)
async def test_reconnect_waits_for_cancelled_attach(
    hass: HomeAssistant, registered_backend: RegisterBackend, method: str
) -> None:
    """A cancelled attach cannot close the replacement connection's session."""
    entry = MockConfigEntry(domain="test_vendor")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    started = asyncio.Event()
    cancelled = asyncio.Event()
    finish_cleanup = asyncio.Event()

    async def delayed_attach(*args: object) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            await finish_cleanup.wait()
            raise

    with patch(method, side_effect=delayed_attach):
        _, unregister = await registered_backend("network", [DESCRIPTOR])
        await started.wait()
        unregister()
        await cancelled.wait()

    backend, _ = await registered_backend("network", [DESCRIPTOR])
    await asyncio.sleep(0)
    finish_cleanup.set()
    await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinators[("network", DESCRIPTOR.dev_eui)]
    assert not coordinator.data.closed
    assert coordinator.last_update_success
    backend.emit(inventory(replace(DESCRIPTOR, name="Replacement"), EventType.UPDATED))
    assert coordinator.data.descriptor.name == "Replacement"
    with patch.object(
        backend, "async_send_downlink", new=AsyncMock(return_value="replacement")
    ) as send:
        await coordinator.data.async_send_downlink(
            data=b"command", f_port=2, wait_for_ack=False
        )
        send.assert_awaited_once()
    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    "error", [ConnectionUnavailable("replay failed"), asyncio.CancelledError()]
)
async def test_failed_reconnect_preserves_devices(
    hass: HomeAssistant, registered_backend: RegisterBackend, error: BaseException
) -> None:
    """A failed reconnect retains the existing model and coordinator for recovery."""
    _, unregister = await registered_backend("network", [DESCRIPTOR])
    entry = MockConfigEntry(domain="test_vendor")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    manager = entry.runtime_data
    coordinator = manager.coordinators[("network", DESCRIPTOR.dev_eui)]
    device = coordinator.data
    unregister()

    with patch.object(_CollectionConnection, "attach", side_effect=error):
        _, unregister = await registered_backend("network", [DESCRIPTOR])
        with pytest.raises(type(error)):
            await manager._tasks["network"]

    assert not device.closed
    assert manager.coordinators[("network", DESCRIPTOR.dev_eui)] is coordinator
    assert not coordinator.last_update_success
    assert hass.states.get("sensor.greenhouse_temperature").state == "unavailable"
    unregister()
    await registered_backend("network", [DESCRIPTOR])
    await hass.async_block_till_done()
    assert manager.coordinators[("network", DESCRIPTOR.dev_eui)] is coordinator
    assert coordinator.data is device
    assert coordinator.last_update_success
    await hass.config_entries.async_unload(entry.entry_id)


async def test_reconnect_during_initial_setup(
    hass: HomeAssistant, registered_backend: RegisterBackend
) -> None:
    """Initial setup and a replacement connection cannot attach concurrently."""
    _, unregister = await registered_backend("network", [DESCRIPTOR])
    entry = MockConfigEntry(domain="test_vendor")
    entry.add_to_hass(hass)
    started = asyncio.Event()
    finish_setup = asyncio.Event()
    setup = ExampleDevices.async_setup

    async def delayed_setup(collection: ExampleDevices) -> None:
        started.set()
        await finish_setup.wait()
        await setup(collection)

    with patch.object(ExampleDevices, "async_setup", new=delayed_setup):
        task = hass.async_create_task(hass.config_entries.async_setup(entry.entry_id))
        await started.wait()
        unregister()
        backend, _ = await registered_backend(
            "network", [replace(DESCRIPTOR, name="Replacement")]
        )
        await asyncio.sleep(0)
        finish_setup.set()
        assert await task
        await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinators[("network", DESCRIPTOR.dev_eui)]
    assert coordinator.data.descriptor.name == "Replacement"
    assert coordinator.last_update_success
    backend.emit(inventory(replace(DESCRIPTOR, name="Updated"), EventType.UPDATED))
    assert coordinator.data.descriptor.name == "Updated"
    await hass.config_entries.async_unload(entry.entry_id)
