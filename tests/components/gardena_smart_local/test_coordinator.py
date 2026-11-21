"""Tests for the GARDENA smart local coordinator."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from gardena_smart_local_api.client import DiscoveryError, GatewayClient, RequestError
from gardena_smart_local_api.devices import DeviceMap
from gardena_smart_local_api.devices.irrigation import Gen2WaterControl
from gardena_smart_local_api.messages import Event, IngressMessageList, Reply
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.gardena_smart_local.const import (
    CONF_FINGERPRINT,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.components.gardena_smart_local.coordinator import (
    GardenaSmartLocalCoordinator,
    IncludableDeviceInfo,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

MOCK_DATA = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: DEFAULT_PORT,
    CONF_PASSWORD: "testpassword",
    CONF_FINGERPRINT: "ab" * 32,
}


@pytest.fixture
async def coordinator(hass: HomeAssistant) -> GardenaSmartLocalCoordinator:
    """Return a coordinator that is not connected to a gateway."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)
    return GardenaSmartLocalCoordinator(
        hass,
        entry,
        MOCK_DATA[CONF_HOST],
        MOCK_DATA[CONF_PORT],
        MOCK_DATA[CONF_PASSWORD],
        MOCK_DATA[CONF_FINGERPRINT],
    )


async def test_schedule_unknown_device_discovery_debounces_burst(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A burst of events for unknown devices schedules only one re-discovery run."""
    with patch.object(coordinator.hass.loop, "call_later") as call_later:
        coordinator._schedule_unknown_device_discovery("dev-1")
        coordinator._schedule_unknown_device_discovery("dev-1")
        coordinator._schedule_unknown_device_discovery("dev-2")

    call_later.assert_called_once()
    assert coordinator._unknown_device_discovery_handle is not None


async def test_schedule_unknown_device_discovery_skips_including_device(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A device this coordinator is actively including must not auto-discover."""
    coordinator._including_device_ids.add("dev-1")

    with patch.object(coordinator.hass.loop, "call_later") as call_later:
        coordinator._schedule_unknown_device_discovery("dev-1")

    call_later.assert_not_called()
    assert coordinator._unknown_device_discovery_handle is None


async def test_discover_unknown_devices_runs_full_discovery(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """The debounced run re-discovers and clears its handle when done."""
    coordinator._unknown_device_discovery_handle = coordinator.hass.loop.call_later(
        99, lambda: None
    )

    with patch.object(coordinator, "_do_discovery", AsyncMock()) as do_discovery:
        await coordinator._discover_unknown_devices()

    do_discovery.assert_awaited_once()
    assert coordinator._unknown_device_discovery_handle is None


async def test_discover_unknown_devices_failure_clears_handle(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A failed re-discovery still clears the handle, so a later event can retry."""
    coordinator._unknown_device_discovery_handle = coordinator.hass.loop.call_later(
        99, lambda: None
    )

    with patch.object(
        coordinator, "_do_discovery", AsyncMock(side_effect=RuntimeError("boom"))
    ):
        await coordinator._discover_unknown_devices()

    assert coordinator._unknown_device_discovery_handle is None


async def test_async_disconnect_cancels_pending_rediscovery(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Disconnecting cancels a re-discovery run still in flight."""
    coordinator._unknown_device_discovery_handle = coordinator.hass.loop.call_later(
        99, lambda: None
    )

    async def _hang() -> None:
        # Stands in for a gateway round trip that never returns; the test
        # only cares that async_disconnect cancels it, not that it finishes.
        await asyncio.sleep(3600)

    with patch.object(coordinator, "_do_discovery", side_effect=_hang):
        coordinator._unknown_device_discovery_task = coordinator.hass.async_create_task(
            coordinator._discover_unknown_devices()
        )
        await asyncio.sleep(0)  # let the task start and reach the sleep

        await coordinator.async_disconnect()

    assert coordinator._unknown_device_discovery_handle is None
    assert coordinator._unknown_device_discovery_task is None


async def test_exclude_already_absent_device_succeeds(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Excluding a device already gone from the map counts as success.

    A delete event or a fresh discovery can remove it first (e.g. it was
    excluded through the official app); there is nothing left to reject,
    so this must not report a failure that creates a misleading repair
    issue.
    """
    assert await coordinator.async_exclude_device("dev-1") is True


def _excludable_device() -> MagicMock:
    device = MagicMock()
    device.id = "dev-1"
    device.build_exclusion_obj.return_value = "EXCLUDE_OBJ"
    return device


async def test_exclude_success_drops_device(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A confirmed exclusion removes the device for good."""
    device = _excludable_device()
    coordinator._devices = {device.id: device}

    with patch.object(
        coordinator.client,
        "send_request",
        AsyncMock(return_value=[Reply(request_id="1", success=True)]),
    ):
        assert await coordinator.async_exclude_device(device.id) is True

    assert device.id not in coordinator._devices
    assert not coordinator._excluding


@pytest.mark.parametrize(
    "outcome",
    [
        TimeoutError(),
        ConnectionError("not connected"),
        RequestError("rejected", IngressMessageList([])),
        RuntimeError("boom"),
    ],
)
async def test_exclude_failure_keeps_device(
    coordinator: GardenaSmartLocalCoordinator, outcome: object
) -> None:
    """A device the gateway did not release keeps its state."""
    device = _excludable_device()
    coordinator._devices = {device.id: device}
    send = AsyncMock(side_effect=outcome)

    with patch.object(coordinator.client, "send_request", send):
        assert await coordinator.async_exclude_device(device.id) is False

    assert coordinator._devices[device.id] is device
    assert not coordinator._excluding


async def test_discovery_during_exclusion_does_not_restore_device(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A discovery finishing mid-exclusion must not bring the device back."""
    device = _excludable_device()
    coordinator._devices = {device.id: device}

    async def _send(*args: object, **kwargs: object) -> list[Reply]:
        coordinator._update_devices({device.id: device})
        assert device.id not in coordinator._devices
        return [Reply(request_id="1", success=True)]

    with patch.object(coordinator.client, "send_request", _send):
        assert await coordinator.async_exclude_device(device.id) is True

    assert device.id not in coordinator._devices


async def test_event_during_exclusion_does_not_schedule_discovery(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Events of a device being excluded are not mistaken for a new device."""
    coordinator._excluding["dev-1"] = _excludable_device()
    event = MagicMock()
    event.entity.path.object_name = "valve"
    event.entity.device = "dev-1"
    event.op = "update"

    assert await coordinator._handle_event(event) is False

    assert coordinator._unknown_device_discovery_handle is None


async def test_event_during_running_rediscovery_queues_one_more_pass(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A device announced while a re-discovery runs is picked up by a follow-up."""
    coordinator._unknown_device_discovery_handle = coordinator.hass.loop.call_later(
        99, lambda: None
    )
    running = coordinator.hass.async_create_task(asyncio.sleep(3600))
    coordinator._unknown_device_discovery_task = running

    coordinator._schedule_unknown_device_discovery("dev-2")
    coordinator._schedule_unknown_device_discovery("dev-3")
    assert coordinator._rediscovery_pending is True

    with patch.object(coordinator, "_do_discovery", AsyncMock()):
        await coordinator._discover_unknown_devices()

    assert coordinator._rediscovery_pending is False
    assert coordinator._unknown_device_discovery_handle is not None
    coordinator._unknown_device_discovery_handle.cancel()
    running.cancel()


async def test_event_before_rediscovery_starts_queues_nothing(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A run that has not started yet already covers a new unknown device."""
    coordinator._schedule_unknown_device_discovery("dev-1")
    coordinator._schedule_unknown_device_discovery("dev-2")

    assert coordinator._rediscovery_pending is False
    assert coordinator._unknown_device_discovery_handle is not None
    coordinator._unknown_device_discovery_handle.cancel()


async def test_disconnect_does_not_rearm_rediscovery(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A cancelled run does not schedule its follow-up pass."""
    coordinator._rediscovery_pending = True

    async def _hang() -> None:
        await asyncio.sleep(3600)

    with patch.object(coordinator, "_do_discovery", side_effect=_hang):
        coordinator._unknown_device_discovery_task = coordinator.hass.async_create_task(
            coordinator._discover_unknown_devices()
        )
        await asyncio.sleep(0)
        await coordinator.async_disconnect()

    assert coordinator._unknown_device_discovery_handle is None
    assert coordinator._rediscovery_pending is False


async def test_inclusion_completing_during_last_wait_succeeds(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """The device leaving includable state in the final second is a success."""
    info = IncludableDeviceInfo("inst-1", "svc", "dev-1", "Valve", True)
    coordinator._includable_devices["inst-1"] = info

    async def _sleep(_delay: float) -> None:
        coordinator._includable_devices.pop("inst-1", None)

    async def _discover(broadcast: bool = True) -> None:
        coordinator._devices = {"dev-1": MagicMock()}

    with (
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.INCLUSION_TIMEOUT",
            1,
        ),
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.asyncio.sleep",
            _sleep,
        ),
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.build_inclusion_obj"
        ),
        patch.object(
            coordinator.client,
            "send_request",
            AsyncMock(return_value=[Reply(request_id="1", success=True)]),
        ),
        patch.object(coordinator, "_do_discovery", _discover),
    ):
        assert await coordinator.async_include_device("inst-1") == "dev-1"


async def test_inclusion_timeout_when_device_never_leaves(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A device still in inclusion mode after the timeout is a failure."""
    info = IncludableDeviceInfo("inst-1", "svc", "dev-1", "Valve", True)
    coordinator._includable_devices["inst-1"] = info

    with (
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.INCLUSION_TIMEOUT",
            1,
        ),
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.asyncio.sleep",
            AsyncMock(),
        ),
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.build_inclusion_obj"
        ),
        patch.object(
            coordinator.client,
            "send_request",
            AsyncMock(return_value=[Reply(request_id="1", success=True)]),
        ),
    ):
        assert await coordinator.async_include_device("inst-1") is None


def _event(
    device: str | None = "dev-1",
    op: str = "update",
    object_name: str | None = "valve",
    instance_id: str | None = None,
    service: str | None = None,
    payload: dict | None = None,
) -> MagicMock:
    event = MagicMock()
    event.__class__ = Event
    event.op = op
    event.entity.device = device
    event.entity.path.object_name = object_name
    event.entity.path.object_instance_id = instance_id
    event.entity.service = service
    event.payload = payload or {}
    return event


async def test_handle_event_routes_includable_events(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Includable device events go to the inclusion tracking."""
    event = _event(object_name="includable_device")

    with patch.object(coordinator, "_handle_includable_event", AsyncMock()) as handle:
        assert await coordinator._handle_event(event) is False

    handle.assert_awaited_once_with(event)


async def test_handle_event_ignores_events_without_device(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """An event that names no device cannot be applied."""
    assert await coordinator._handle_event(_event(device=None)) is False


async def test_handle_event_delete_drops_known_device(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A delete event for the whole device removes it from the map."""
    coordinator._devices = {"dev-1": MagicMock()}

    assert (
        await coordinator._handle_event(_event(op="delete", object_name=None)) is False
    )

    assert "dev-1" not in coordinator._devices


async def test_handle_event_unknown_device_schedules_discovery(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """An update for an unknown device triggers a re-discovery, a delete does not."""
    assert await coordinator._handle_event(_event(op="delete")) is False
    assert coordinator._unknown_device_discovery_handle is None

    assert await coordinator._handle_event(_event(op="update")) is False

    assert coordinator._unknown_device_discovery_handle is not None
    coordinator._unknown_device_discovery_handle.cancel()


async def test_handle_event_updates_known_device(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """An update for a known device is applied to it."""
    device = MagicMock()
    device.is_online = True
    coordinator._devices = {"dev-1": device}
    event = _event()

    def _go_offline(_event: Event) -> None:
        device.is_online = False

    device.update_data.side_effect = _go_offline

    assert await coordinator._handle_event(event) is True

    device.update_data.assert_called_once_with(event)


async def test_includable_event_without_instance_is_ignored(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """An includable event without an instance id cannot be tracked."""
    await coordinator._handle_includable_event(_event(instance_id=None))

    assert not coordinator._includable_devices
    assert not coordinator._includable_timeouts


async def test_includable_event_delete_forgets_device(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A delete event removes the device and cancels its heartbeat timeout."""
    handle = MagicMock()
    coordinator._includable_timeouts["inst-1"] = handle
    coordinator._includable_devices["inst-1"] = IncludableDeviceInfo(
        "inst-1", "svc", "dev-1", "Valve", True
    )

    await coordinator._handle_includable_event(
        _event(op="delete", instance_id="inst-1")
    )

    handle.cancel.assert_called_once()
    assert not coordinator._includable_devices
    assert not coordinator._includable_timeouts


@pytest.mark.parametrize(
    ("service", "payload"),
    [
        (None, {"identifier": {"vs": "abc"}}),
        ("svc", {}),
    ],
)
async def test_includable_event_without_service_or_identifier(
    coordinator: GardenaSmartLocalCoordinator,
    service: str | None,
    payload: dict,
) -> None:
    """An event that cannot identify the device is not tracked as includable."""
    await coordinator._handle_includable_event(
        _event(instance_id="inst-1", service=service, payload=payload)
    )

    assert not coordinator._includable_devices
    coordinator._includable_timeouts["inst-1"].cancel()


async def test_includable_event_with_unparsable_identifier(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """An identifier that is not an SGTIN is ignored."""
    await coordinator._handle_includable_event(
        _event(
            instance_id="inst-1", service="svc", payload={"identifier": {"vs": "nope"}}
        )
    )

    assert not coordinator._includable_devices
    coordinator._includable_timeouts["inst-1"].cancel()


async def test_includable_event_tracks_supported_device(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A valid event registers the device, and a heartbeat only re-arms the timeout."""
    sgtin = MagicMock(item_reference=1, serial=5)
    sgtin.get_model_name = AsyncMock(return_value="Water Control")
    event = _event(
        instance_id="inst-1", service="svc", payload={"identifier": {"vs": "abc"}}
    )

    with (
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.SGTIN96Info"
        ) as sgtin_info,
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.MODEL_NUMBER_MAP",
            {1: Gen2WaterControl},
        ),
    ):
        sgtin_info.from_hex.return_value = sgtin
        await coordinator._handle_includable_event(event)
        await coordinator._handle_includable_event(event)

    assert coordinator.includable_devices == {
        "inst-1": IncludableDeviceInfo(
            "inst-1", "svc", "abc", "Water Control 00000005", True
        )
    }
    sgtin_info.from_hex.assert_called_once_with("abc")
    coordinator._includable_timeouts["inst-1"].cancel()


async def test_includable_device_expires_without_heartbeat(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A device that stops announcing itself is forgotten."""
    coordinator._includable_devices["inst-1"] = IncludableDeviceInfo(
        "inst-1", "svc", "dev-1", "Valve", True
    )
    coordinator._includable_timeouts["inst-1"] = MagicMock()

    coordinator._expire_includable("inst-1")

    assert not coordinator._includable_devices
    assert not coordinator._includable_timeouts


async def test_includable_devices_lists_supported_only(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Unsupported devices are tracked but not offered for inclusion."""
    coordinator._includable_devices["a"] = IncludableDeviceInfo(
        "a", "s", "d1", "A", True
    )
    coordinator._includable_devices["b"] = IncludableDeviceInfo(
        "b", "s", "d2", "B", False
    )

    assert list(coordinator.includable_devices) == ["a"]


@pytest.mark.parametrize(
    ("instance_id", "supported"), [("missing", True), ("inst-1", False)]
)
async def test_include_rejects_unknown_or_unsupported_device(
    coordinator: GardenaSmartLocalCoordinator, instance_id: str, supported: bool
) -> None:
    """Only a known, supported device can be included."""
    coordinator._includable_devices["inst-1"] = IncludableDeviceInfo(
        "inst-1", "svc", "dev-1", "Valve", supported
    )

    assert await coordinator.async_include_device(instance_id) is None


@pytest.mark.parametrize(
    "outcome",
    [
        TimeoutError(),
        ConnectionError("not connected"),
        RequestError("rejected", IngressMessageList([])),
        RuntimeError("boom"),
    ],
)
async def test_include_fails_when_gateway_refuses(
    coordinator: GardenaSmartLocalCoordinator, outcome: object
) -> None:
    """A failed or rejected inclusion request reports failure."""
    coordinator._includable_devices["inst-1"] = IncludableDeviceInfo(
        "inst-1", "svc", "dev-1", "Valve", True
    )
    send = AsyncMock(side_effect=outcome)

    with (
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.build_inclusion_obj"
        ),
        patch.object(coordinator.client, "send_request", send),
    ):
        assert await coordinator.async_include_device("inst-1") is None

    assert not coordinator._including_device_ids


async def test_include_fails_when_discovery_does_not_find_device(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A device missing from the post-inclusion discovery is a failure."""
    coordinator._includable_devices["inst-1"] = IncludableDeviceInfo(
        "inst-1", "svc", "dev-1", "Valve", True
    )

    async def _send(*args: object, **kwargs: object) -> list[Reply]:
        # The gateway takes the device out of inclusion mode right away.
        coordinator._includable_devices.pop("inst-1")
        return [Reply(request_id="1", success=True)]

    with (
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.build_inclusion_obj"
        ),
        patch.object(coordinator.client, "send_request", _send),
        patch.object(coordinator, "_do_discovery", AsyncMock()),
    ):
        assert await coordinator.async_include_device("inst-1") is None


async def test_include_fails_when_rediscovery_errors(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A failing post-inclusion discovery reports failure."""
    coordinator._includable_devices["inst-1"] = IncludableDeviceInfo(
        "inst-1", "svc", "dev-1", "Valve", True
    )

    async def _leave(_delay: float) -> None:
        coordinator._includable_devices.pop("inst-1", None)

    with (
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.build_inclusion_obj"
        ),
        patch.object(
            coordinator.client,
            "send_request",
            AsyncMock(return_value=[Reply(request_id="1", success=True)]),
        ),
        patch.object(
            coordinator, "_do_discovery", AsyncMock(side_effect=RuntimeError("boom"))
        ),
        patch(
            "homeassistant.components.gardena_smart_local.coordinator.asyncio.sleep",
            _leave,
        ),
    ):
        assert await coordinator.async_include_device("inst-1") is None


async def test_drop_unknown_device_changes_nothing(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Dropping a device the map does not hold publishes nothing."""
    updated = MagicMock()
    with patch.object(coordinator, "async_set_updated_data", updated):
        coordinator.async_drop_device("dev-1")

    updated.assert_not_called()


async def test_update_devices_replaces_the_map(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A full discovery adds new devices, refreshes known ones and drops gone ones."""
    gone, kept, new = MagicMock(id="gone"), MagicMock(id="kept"), MagicMock(id="new")
    coordinator._devices = {"gone": gone, "kept": kept}
    refreshed = MagicMock(id="kept")

    coordinator._update_devices({"kept": refreshed, "new": new})

    assert coordinator._devices == {"kept": refreshed, "new": new}


async def test_update_devices_survives_a_broken_device(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A device that cannot be applied does not block the devices after it."""
    broken, healthy = MagicMock(id="broken"), MagicMock(id="healthy")
    original = coordinator._update_device

    def _update(device: MagicMock) -> None:
        if device is broken:
            raise RuntimeError("bad")
        original(device)

    with patch.object(coordinator, "_update_device", side_effect=_update):
        coordinator._update_devices({"broken": broken, "healthy": healthy})

    assert list(coordinator._devices.keys()) == ["healthy"]


async def test_update_data_returns_the_device_map(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Refreshing returns the pushed state instead of polling."""
    assert await coordinator._async_update_data() is coordinator._devices


async def test_disconnect_cancels_includable_timeouts(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Disconnecting stops the heartbeat timers of includable devices."""
    handle = MagicMock()
    coordinator._includable_timeouts["inst-1"] = handle

    await coordinator.async_disconnect()

    handle.cancel.assert_called_once()
    assert not coordinator._includable_timeouts


async def test_start_unknown_device_discovery_runs_a_task(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """The debounce timer starts the re-discovery as a task."""
    with patch.object(coordinator, "_do_discovery", AsyncMock()) as discovery:
        coordinator._start_unknown_device_discovery()
        assert coordinator._unknown_device_discovery_task is not None
        await coordinator._unknown_device_discovery_task

    discovery.assert_awaited_once()


async def test_client_is_set_up_for_the_gateway(hass: HomeAssistant) -> None:
    """The client pins the stored fingerprint and reports back to the coordinator."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.gardena_smart_local.coordinator.GatewayClient"
    ) as client_class:
        coordinator = GardenaSmartLocalCoordinator(
            hass,
            entry,
            MOCK_DATA[CONF_HOST],
            MOCK_DATA[CONF_PORT],
            MOCK_DATA[CONF_PASSWORD],
            MOCK_DATA[CONF_FINGERPRINT],
        )

    client_class.assert_called_once_with(
        MOCK_DATA[CONF_HOST],
        MOCK_DATA[CONF_PORT],
        MOCK_DATA[CONF_PASSWORD],
        session=async_get_clientsession(hass),
        fingerprint=MOCK_DATA[CONF_FINGERPRINT],
        on_connect=coordinator._async_on_connect,
        on_event=coordinator._async_on_event,
        on_disconnect=coordinator._on_disconnect,
        on_auth_failed=coordinator._on_auth_failed,
    )
    assert coordinator.client is client_class.return_value


async def test_uri_and_connected_come_from_the_client(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """The coordinator reports what the client knows about the connection."""
    assert coordinator.uri == "wss://192.168.1.100:8443"

    for connected in (True, False):
        with patch.object(
            GatewayClient, "connected", new_callable=PropertyMock
        ) as client_connected:
            client_connected.return_value = connected
            assert coordinator.connected is connected


async def test_connect_and_disconnect_use_the_client(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Connecting and disconnecting is left to the client."""
    with (
        patch.object(coordinator.client, "connect", AsyncMock()) as connect,
        patch.object(coordinator.client, "disconnect", AsyncMock()) as disconnect,
    ):
        await coordinator.async_connect()
        await coordinator.async_disconnect()

    connect.assert_awaited_once_with()
    disconnect.assert_awaited_once_with()


async def test_every_connect_runs_discovery(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """The client hands over each (re)connect, and the devices are discovered."""
    device = MagicMock(id="dev-1")
    discover = AsyncMock(return_value={"dev-1": device})

    with patch.object(coordinator.client, "discover_devices", discover):
        await coordinator._async_on_connect()

    discover.assert_awaited_once()
    assert dict(coordinator.data.items()) == {"dev-1": device}


async def test_failed_discovery_keeps_the_known_devices(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A discovery the gateway answered with an error is not applied."""
    known = MagicMock(id="dev-1")
    coordinator._devices = {"dev-1": known}
    error = DiscoveryError("failed", IngressMessageList([]), DeviceMap({}))

    with (
        patch.object(
            coordinator.client, "discover_devices", AsyncMock(side_effect=error)
        ),
        pytest.raises(DiscoveryError),
    ):
        await coordinator._async_on_connect()

    assert coordinator._devices == {"dev-1": known}


async def test_rejected_password_starts_reauth(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A password the gateway rejects while running starts reauthentication."""
    with patch.object(coordinator.config_entry, "async_start_reauth") as start_reauth:
        coordinator._on_auth_failed()

    start_reauth.assert_called_once_with(coordinator.hass)


async def test_lost_connection_updates_the_entities(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """Entities re-check their availability when the connection drops."""
    with patch.object(coordinator, "async_update_listeners") as update_listeners:
        coordinator._on_disconnect()

    update_listeners.assert_called_once_with()


async def test_event_that_changed_state_is_published(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """An event that changed a device publishes the device map."""
    updated = MagicMock()

    with (
        patch.object(coordinator, "_handle_event", AsyncMock(return_value=True)),
        patch.object(coordinator, "async_set_updated_data", updated),
    ):
        await coordinator._async_on_event(_event())

    updated.assert_called_once_with(coordinator._devices)


async def test_event_that_changed_nothing_is_not_published(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """An event that left every device as it was publishes nothing."""
    updated = MagicMock()

    with (
        patch.object(coordinator, "_handle_event", AsyncMock(return_value=False)),
        patch.object(coordinator, "async_set_updated_data", updated),
    ):
        await coordinator._async_on_event(_event())

    updated.assert_not_called()


async def test_failing_event_is_logged_and_skipped(
    coordinator: GardenaSmartLocalCoordinator, caplog: pytest.LogCaptureFixture
) -> None:
    """One bad event must not stop the events after it."""
    updated = MagicMock()

    with (
        patch.object(
            coordinator, "_handle_event", AsyncMock(side_effect=RuntimeError("bad"))
        ),
        patch.object(coordinator, "async_set_updated_data", updated),
    ):
        await coordinator._async_on_event(_event())

    assert "Error handling event" in caplog.text
    updated.assert_not_called()


async def test_discovery_started_before_an_exclusion_does_not_restore_device(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A snapshot taken before the reset still lists the excluded device."""
    device = _excludable_device()
    other = MagicMock(id="dev-2")
    coordinator._devices = {device.id: device}
    release = asyncio.Event()

    async def _discover(*args: object) -> dict[str, MagicMock]:
        await release.wait()
        return {device.id: device, other.id: other}

    with patch.object(coordinator.client, "discover_devices", _discover):
        discovery = asyncio.create_task(coordinator._do_discovery())
        await asyncio.sleep(0)
        with patch.object(
            coordinator.client,
            "send_request",
            AsyncMock(return_value=[Reply(request_id="1", success=True)]),
        ):
            assert await coordinator.async_exclude_device(device.id) is True
        release.set()
        await discovery

    assert coordinator._devices == {other.id: other}


async def test_discovery_started_after_an_exclusion_sees_the_device_again(
    coordinator: GardenaSmartLocalCoordinator,
) -> None:
    """A device that is included again after its exclusion comes back."""
    device = _excludable_device()
    coordinator._devices = {device.id: device}

    with patch.object(
        coordinator.client,
        "send_request",
        AsyncMock(return_value=[Reply(request_id="1", success=True)]),
    ):
        assert await coordinator.async_exclude_device(device.id) is True

    with patch.object(
        coordinator.client,
        "discover_devices",
        AsyncMock(return_value={device.id: device}),
    ):
        await coordinator._do_discovery()

    assert coordinator._devices == {device.id: device}
