"""Test device observations, connection lifecycle, and overview subscriptions."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch

from lorawan_connection import (
    AddedEvent,
    GatewayReception,
    JoinEvent,
    RemovedEvent,
    StatusEvent,
    UplinkEvent,
)
from lorawan_connection.mock import MockConnection
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    MockUser,
    async_fire_time_changed,
)
from pytest_homeassistant.typing import WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lorawan import async_register_connection
from homeassistant.components.lorawan.websocket_api import _snapshot
from homeassistant.config_entries import SOURCE_IGNORE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import RegisterBackend
from .helpers import DESCRIPTOR


async def test_device_observations(
    hass: HomeAssistant,
    registered_backend: RegisterBackend,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Discovery is not an uplink; retain radio pairs and MAC status independently."""
    backend, _ = await registered_backend("network", [DESCRIPTOR])
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "lorawan/devices/list"})
    result = await client.receive_json()
    assert result["result"] == snapshot(name="discovered")
    now = dt_util.parse_datetime("2026-10-16T12:00:00+00:00")
    assert now is not None
    backend.emit(
        UplinkEvent(
            descriptor=DESCRIPTOR,
            received_at=now,
            data=b"secret payload",
            receptions=(
                GatewayReception("nearby", -45, -1.5),
                GatewayReception("rooftop", -85, 4),
            ),
        )
    )
    backend.emit(JoinEvent(descriptor=DESCRIPTOR, received_at=now, dev_addr="abcdef01"))
    backend.emit(
        StatusEvent(
            descriptor=DESCRIPTOR,
            received_at=now,
            margin=2,
            battery_level=0,
            battery_level_unavailable=False,
        )
    )
    await client.send_json({"id": 2, "type": "lorawan/devices/list"})
    result = await client.receive_json()
    assert result["result"] == snapshot(name="observed")
    assert "secret payload" not in str(result)
    assert "profile_id" not in str(result)
    assert "model_id" not in str(result)


async def test_reconnect_rebuilds_observations(
    hass: HomeAssistant, registered_backend: RegisterBackend
) -> None:
    """Rebuild observations from the backend after a disconnect."""
    second = replace(DESCRIPTOR, dev_eui="0000000000000001")
    backend, _ = await registered_backend("network", [DESCRIPTOR, second])
    now = dt_util.utcnow()
    backend.emit(UplinkEvent(descriptor=DESCRIPTOR, received_at=now, data=b"data"))
    backend.emit(JoinEvent(descriptor=DESCRIPTOR, received_at=now, dev_addr="abcdef01"))
    backend.emit(
        StatusEvent(
            descriptor=DESCRIPTOR,
            received_at=now,
            battery_level=70,
            battery_level_unavailable=False,
            margin=2,
        )
    )
    backend.disconnect()
    result = _snapshot(hass)
    assert result["devices"] == []
    assert result["connections"] == []
    replacement, _ = await registered_backend("network", [DESCRIPTOR])
    states = _snapshot(hass)["devices"]
    assert len(states) == 1
    assert states[0]["last_uplink"] is None
    assert states[0]["last_join"] is None
    assert states[0]["last_status"] is None
    assert states[0]["battery_level"] is None
    assert states[0]["downlink_margin"] is None
    observed_at = now - timedelta(hours=1)
    replacement.emit(
        UplinkEvent(descriptor=DESCRIPTOR, received_at=observed_at, data=b"history")
    )
    assert _snapshot(hass)["devices"][0]["last_uplink"] == observed_at.isoformat()
    replacement.emit(RemovedEvent(descriptor=DESCRIPTOR))
    assert _snapshot(hass)["devices"] == []
    replacement.emit(AddedEvent(descriptor=DESCRIPTOR))
    assert _snapshot(hass)["devices"][0]["last_uplink"] is None


async def test_same_eui_on_two_connections(
    hass: HomeAssistant, registered_backend: RegisterBackend
) -> None:
    """Connections own separate observations even when DevEUIs match."""
    backend, _ = await registered_backend("network", [DESCRIPTOR])
    await registered_backend("other", [replace(DESCRIPTOR, network_id="other")])
    backend.emit(
        StatusEvent(
            descriptor=DESCRIPTOR,
            received_at=dt_util.utcnow(),
            battery_level=70,
            battery_level_unavailable=False,
        )
    )
    first, second = _snapshot(hass)["devices"]
    assert first["battery_level"] == 70
    assert second["battery_level"] is None


@pytest.mark.parametrize("event_class", [UplinkEvent, JoinEvent, StatusEvent])
async def test_delayed_observations(
    hass: HomeAssistant,
    registered_backend: RegisterBackend,
    event_class: type[UplinkEvent | JoinEvent | StatusEvent],
) -> None:
    """Delayed events cannot move observation timestamps backwards."""
    backend, _ = await registered_backend("network", [DESCRIPTOR])
    now = dt_util.utcnow()
    events = {
        UplinkEvent: UplinkEvent(descriptor=DESCRIPTOR, received_at=now, data=b"new"),
        JoinEvent: JoinEvent(descriptor=DESCRIPTOR, received_at=now, dev_addr="1234"),
        StatusEvent: StatusEvent(descriptor=DESCRIPTOR, received_at=now),
    }
    event = events[event_class]
    backend.emit(event)
    expected = _snapshot(hass)
    backend.emit(replace(event, received_at=now - timedelta(hours=1)))
    assert _snapshot(hass) == expected


@pytest.mark.parametrize(
    ("external_power", "unavailable", "expected"),
    [(True, False, None), (False, True, None), (False, False, 0)],
)
async def test_battery_states(
    hass: HomeAssistant,
    registered_backend: RegisterBackend,
    external_power: bool,
    unavailable: bool,
    expected: int | None,
) -> None:
    """Distinguish empty batteries, external power, and unreported battery levels."""
    backend, _ = await registered_backend("network", [DESCRIPTOR])
    backend.emit(
        StatusEvent(
            descriptor=DESCRIPTOR,
            received_at=dt_util.utcnow(),
            external_power_source=external_power,
            battery_level_unavailable=unavailable,
        )
    )
    device = _snapshot(hass)["devices"][0]
    assert device["battery_level"] == expected
    assert device["external_power_source"] is external_power


@pytest.mark.parametrize("entry_id", ["network", "different_entry_id"])
async def test_support_and_registry_link(
    hass: HomeAssistant,
    registered_backend: RegisterBackend,
    device_registry: dr.DeviceRegistry,
    entry_id: str,
) -> None:
    """Report setup guidance and use the registry's device ID and user name."""
    backend, _ = await registered_backend(entry_id, [DESCRIPTOR])
    assert _snapshot(hass)["devices"][0]["support"] == "integration_not_configured"
    entry = MockConfigEntry(domain="test_vendor")
    entry.add_to_hass(hass)
    assert _snapshot(hass)["devices"][0]["support"] == "unsupported_model"
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(entry.domain, f"network:{DESCRIPTOR.dev_eui}")},
        name="Original name",
        manufacturer="Seeed Studio",
        model="S2103",
    )
    device_registry.async_update_device(device.id, name_by_user="Office")
    result = _snapshot(hass)["devices"][0]
    assert result["device_id"] == device.id
    assert result["name"] == "Office"
    assert result["manufacturer"] == "Seeed Studio"
    assert result["model"] == "S2103"
    assert result["support"] == "supported"
    backend.emit(
        AddedEvent(
            descriptor=replace(DESCRIPTOR, dev_eui="0000000000000001", brand_id=None)
        )
    )
    assert _snapshot(hass)["devices"][1]["support"] == "missing_identity"
    assert len(device_registry.devices) == 1


async def test_ignored_vendor_entry(
    hass: HomeAssistant,
    registered_backend: RegisterBackend,
) -> None:
    """Ignored discovery entries do not configure a device integration."""
    await registered_backend("network", [DESCRIPTOR])
    entry = MockConfigEntry(domain="test_vendor", source=SOURCE_IGNORE)
    entry.add_to_hass(hass)
    assert _snapshot(hass)["devices"][0]["support"] == "integration_not_configured"


async def test_subscribe_unsubscribe(
    hass: HomeAssistant,
    registered_backend: RegisterBackend,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Stream live snapshots and stop delivering when the client unsubscribes."""
    backend, _ = await registered_backend("network", [DESCRIPTOR])
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "lorawan/devices/subscribe"})
    assert (await client.receive_json())["success"]
    assert (await client.receive_json())["event"]["devices"][0]["last_uplink"] is None
    now = dt_util.utcnow()
    backend.emit(UplinkEvent(descriptor=DESCRIPTOR, received_at=now, data=b"data"))
    async_fire_time_changed(hass, now + timedelta(seconds=1))
    assert (await client.receive_json())["event"]["devices"][0][
        "last_uplink"
    ] == now.isoformat()
    backend.disconnect()
    async_fire_time_changed(hass, now + timedelta(seconds=1))
    event = (await client.receive_json())["event"]
    assert event["devices"] == []
    assert event["connections"] == []
    await client.send_json({"id": 2, "type": "unsubscribe_events", "subscription": 1})
    assert (await client.receive_json())["success"]
    with patch("homeassistant.components.lorawan.websocket_api._snapshot") as snapshot:
        await registered_backend("network", [DESCRIPTOR])
        await hass.async_block_till_done()
        snapshot.assert_not_called()


async def test_subscription_config_entry_changes(
    hass: HomeAssistant,
    registered_backend: RegisterBackend,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Follow connection names only while the client is subscribed."""
    await registered_backend("network", [DESCRIPTOR])
    entry = hass.config_entries.async_get_entry("network")
    assert entry is not None
    unrelated = MockConfigEntry(domain="unrelated")
    unrelated.add_to_hass(hass)
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "lorawan/devices/subscribe"})
    assert (await client.receive_json())["success"]
    await client.receive_json()

    with patch(
        "homeassistant.components.lorawan.websocket_api._snapshot", wraps=_snapshot
    ) as snapshot:
        hass.config_entries.async_update_entry(unrelated, title="Unrelated")
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
        await hass.async_block_till_done()
        snapshot.assert_not_called()

        hass.config_entries.async_update_entry(entry, title="Garden")
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
        assert (await client.receive_json())["event"]["connections"][0][
            "title"
        ] == "Garden"
        snapshot.assert_called_once_with(hass)

    await client.send_json({"id": 2, "type": "unsubscribe_events", "subscription": 1})
    assert (await client.receive_json())["success"]
    with patch(
        "homeassistant.components.lorawan.websocket_api.Debouncer.async_schedule_call"
    ) as schedule:
        hass.config_entries.async_update_entry(entry, title="Home")
        await hass.async_block_till_done()
        schedule.assert_not_called()


async def test_subscription_batches_updates(
    hass: HomeAssistant,
    registered_backend: RegisterBackend,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """A burst produces one snapshot with the latest observations."""
    descriptors = [replace(DESCRIPTOR, dev_eui=f"{index:016x}") for index in range(20)]
    backend, _ = await registered_backend("network", descriptors)
    client = await hass_ws_client(hass)
    with patch(
        "homeassistant.components.lorawan.websocket_api._snapshot", wraps=_snapshot
    ) as snapshot:
        await client.send_json({"id": 1, "type": "lorawan/devices/subscribe"})
        assert (await client.receive_json())["success"]
        assert len((await client.receive_json())["event"]["devices"]) == 20
        snapshot.assert_called_once_with(hass)
        snapshot.reset_mock()
        now = dt_util.utcnow()
        for descriptor in descriptors:
            backend.emit(
                UplinkEvent(descriptor=descriptor, received_at=now, data=b"data")
            )
        await hass.async_block_till_done()
        snapshot.assert_not_called()
        async_fire_time_changed(hass, now + timedelta(seconds=1))
        event = (await client.receive_json())["event"]
        assert len(event["devices"]) == 20
        assert all(
            device["last_uplink"] == now.isoformat() for device in event["devices"]
        )
        snapshot.assert_called_once_with(hass)

        snapshot.reset_mock()
        backend.disconnect()
        await client.send_json(
            {"id": 2, "type": "unsubscribe_events", "subscription": 1}
        )
        assert (await client.receive_json())["success"]
        async_fire_time_changed(hass, now + timedelta(seconds=2))
        await hass.async_block_till_done()
        snapshot.assert_not_called()


async def test_subscription_registry_changes(
    hass: HomeAssistant,
    registered_backend: RegisterBackend,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Track registry links appearing, changing, and disappearing."""
    await registered_backend("different_entry_id", [DESCRIPTOR])
    entry = MockConfigEntry(domain="test_vendor")
    entry.add_to_hass(hass)
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "lorawan/devices/subscribe"})
    assert (await client.receive_json())["success"]
    assert (await client.receive_json())["event"]["devices"][0]["device_id"] is None

    identifier = (entry.domain, f"{DESCRIPTOR.network_id}:{DESCRIPTOR.dev_eui}")
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={identifier}, name="Original"
    )
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    result = (await client.receive_json())["event"]["devices"][0]
    assert result["device_id"] == device.id
    assert result["name"] == "Original"

    device_registry.async_update_device(device.id, name_by_user="Office")
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    assert (await client.receive_json())["event"]["devices"][0]["name"] == "Office"

    device_registry.async_remove_device(device.id)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    result = (await client.receive_json())["event"]["devices"][0]
    assert result["device_id"] is None
    assert result["support"] == "unsupported_model"

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(entry.domain, "unrelated")}
    )
    await hass.async_block_till_done()
    device_registry.async_update_device(device.id, new_identifiers={identifier})
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    assert (await client.receive_json())["event"]["devices"][0][
        "device_id"
    ] == device.id

    device_registry.async_update_device(
        device.id, new_identifiers={(entry.domain, "unrelated")}
    )
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    assert (await client.receive_json())["event"]["devices"][0]["device_id"] is None


@pytest.mark.parametrize(
    ("domain", "expected_snapshots"), [("unrelated", 0), ("test_vendor", 1)]
)
async def test_subscription_filters_registry_domains(
    hass: HomeAssistant,
    registered_backend: RegisterBackend,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    domain: str,
    expected_snapshots: int,
) -> None:
    """Use the owning integration domain without inspecting device identifiers."""
    await registered_backend("network", [DESCRIPTOR])
    entry = MockConfigEntry(domain=domain)
    entry.add_to_hass(hass)
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "lorawan/devices/subscribe"})
    assert (await client.receive_json())["success"]
    await client.receive_json()
    with patch(
        "homeassistant.components.lorawan.websocket_api._snapshot", wraps=_snapshot
    ) as snapshot:
        device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id, identifiers={("hardware", "unrelated")}
        )
        await hass.async_block_till_done()
        device_registry.async_update_device(device.id, name_by_user="Unrelated")
        await hass.async_block_till_done()
        device_registry.async_remove_device(device.id)
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
        await hass.async_block_till_done()
        assert snapshot.call_count == expected_snapshots


@pytest.mark.parametrize("command", ["list", "subscribe"])
async def test_admin_required(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    command: str,
    hass_admin_user: MockUser,
) -> None:
    """LoRaWAN metadata is only available to administrators."""
    hass_admin_user.groups = []
    assert await async_setup_component(hass, "lorawan", {})
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": f"lorawan/devices/{command}"})
    assert (await client.receive_json())["error"]["code"] == "unauthorized"


async def test_removed_connection_entry(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    mock_connection: MockConnection,
) -> None:
    """Removing a connection entry removes its devices and metadata."""
    assert await hass.config_entries.async_setup(connection_entry.entry_id)
    mock_connection.emit(AddedEvent(descriptor=DESCRIPTOR))
    result = _snapshot(hass)
    assert len(result["devices"]) == 1
    assert len(result["connections"]) == 1
    await hass.config_entries.async_remove(connection_entry.entry_id)
    await hass.async_block_till_done()
    assert _snapshot(hass) == {"devices": [], "connections": []}


async def test_configuration_url_without_devices(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Offer the console while connected, even before any devices exist."""
    assert await async_setup_component(hass, "lorawan", {})
    backend = MockConnection()
    configuration_url = "https://eu1.cloud.thethings.network/console"
    unsubscribe = await async_register_connection(
        hass, connection_entry, connection=backend, configuration_url=configuration_url
    )
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "lorawan/devices/list"})
    result = (await client.receive_json())["result"]
    assert result["devices"] == []
    assert result["connections"][0]["configuration_url"] == configuration_url
    backend.disconnect()
    assert _snapshot(hass) == {"devices": [], "connections": []}
    unsubscribe()
