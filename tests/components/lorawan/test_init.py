"""Connection registration, vendor discovery, and subscription cleanup."""

import asyncio
from collections.abc import Callable
from dataclasses import replace
from unittest.mock import AsyncMock, Mock, patch

from lorawan_connection import (
    AddedEvent,
    ConnectionUnavailable,
    DeviceEvent,
    Downlink,
    RemovedEvent,
    StatusEvent,
    UpdatedEvent,
    UplinkEvent,
)
from lorawan_connection.mock import MockConnection
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.lorawan import async_register_connection
from homeassistant.components.lorawan.connection import DATA_REGISTRY
from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.lorawan import LoRaWANDiscoveryInfo
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import RegisterBackend
from .helpers import DESCRIPTOR


async def test_registration_and_reconnect(
    hass: HomeAssistant, registered_backend: RegisterBackend
) -> None:
    """The registry tracks active connections, withdrawals, and replacements."""
    first, unregister = await registered_backend("network", [DESCRIPTOR])
    assert hass.data[DATA_REGISTRY].connections["network"].connection is first
    events = Mock()
    stop_events = await first.async_subscribe(
        brands=frozenset({("example", 123)}), listener=events
    )
    events.assert_called_once()
    first.emit(
        UpdatedEvent(
            descriptor=replace(DESCRIPTOR, name="Renamed"), received_at=dt_util.utcnow()
        )
    )
    assert events.call_count == 2
    queue_id = await first.async_send_downlink(
        Downlink(DESCRIPTOR.dev_eui, 1, b"command")
    )
    assert first.downlinks[queue_id].data == b"command"
    first.disconnect()
    assert not hass.data[DATA_REGISTRY].connections
    unregister()
    second, unregister_second = await registered_backend("network", [DESCRIPTOR])
    assert hass.data[DATA_REGISTRY].connections["network"].connection is second
    stop_events()
    unregister_second()
    assert not hass.data[DATA_REGISTRY].connections


async def test_discovery_replay_and_live_events(
    hass: HomeAssistant, registered_backend: RegisterBackend
) -> None:
    """Discover once per connection replay and for each later device addition."""
    with patch(
        "homeassistant.components.lorawan.connection.discovery_flow.async_create_flow"
    ) as discover:
        backend, _ = await registered_backend(
            "network", [DESCRIPTOR, replace(DESCRIPTOR, dev_eui="0201010101010102")]
        )
        discover.assert_called_once_with(
            hass,
            "test_vendor",
            context={"source": SOURCE_INTEGRATION_DISCOVERY},
            data=LoRaWANDiscoveryInfo(),
        )
        backend.emit(UpdatedEvent(descriptor=DESCRIPTOR, received_at=dt_util.utcnow()))
        backend.emit(
            AddedEvent(
                descriptor=replace(DESCRIPTOR, dev_eui="0201010101010103"),
                received_at=dt_util.utcnow(),
            )
        )
        assert discover.call_count == 2
        backend.emit(
            AddedEvent(
                descriptor=replace(DESCRIPTOR, dev_eui="0201010101010104"),
                received_at=dt_util.utcnow(),
            )
        )
        assert discover.call_count == 3
        backend.emit(RemovedEvent(descriptor=DESCRIPTOR, received_at=dt_util.utcnow()))
        backend.emit(
            AddedEvent(
                descriptor=replace(DESCRIPTOR, brand_id=456),
                received_at=dt_util.utcnow(),
            )
        )
        assert discover.call_count == 3
        await registered_backend(
            "other",
            [
                replace(DESCRIPTOR, network_id="other"),
                replace(DESCRIPTOR, network_id="other", dev_eui="0201010101010102"),
            ],
        )
        assert discover.call_count == 4
        backend.disconnect()
        await registered_backend(
            "network", [DESCRIPTOR, replace(DESCRIPTOR, dev_eui="0201010101010102")]
        )
        assert discover.call_count == 5


@pytest.mark.parametrize("event_class", [UpdatedEvent, RemovedEvent])
async def test_discovery_ignores_updates_and_removals(
    hass: HomeAssistant,
    registered_backend: RegisterBackend,
    event_class: type[UpdatedEvent | RemovedEvent],
) -> None:
    """Only additions can discover a vendor, even if it has not been seen before."""
    with patch(
        "homeassistant.components.lorawan.connection.discovery_flow.async_create_flow"
    ) as discover:
        backend, _ = await registered_backend("network", [])
        backend.emit(UpdatedEvent(descriptor=DESCRIPTOR, received_at=dt_util.utcnow()))
        backend.emit(event_class(descriptor=DESCRIPTOR, received_at=dt_util.utcnow()))
        discover.assert_not_called()
        backend.emit(AddedEvent(descriptor=DESCRIPTOR, received_at=dt_util.utcnow()))
        discover.assert_called_once()


async def test_discovery_ignores_device_activity(
    hass: HomeAssistant, registered_backend: RegisterBackend
) -> None:
    """Uplink and status traffic does not start discovery."""
    with patch(
        "homeassistant.components.lorawan.connection.discovery_flow.async_create_flow"
    ) as discover:
        backend, _ = await registered_backend("network", [])
        backend.emit(UpdatedEvent(descriptor=DESCRIPTOR, received_at=dt_util.utcnow()))
        backend.emit(
            UplinkEvent(
                descriptor=DESCRIPTOR, received_at=dt_util.utcnow(), data=b"payload"
            )
        )
        backend.emit(StatusEvent(descriptor=DESCRIPTOR, received_at=dt_util.utcnow()))
        discover.assert_not_called()


async def test_discovery_of_another_vendor(
    hass: HomeAssistant, registered_backend: RegisterBackend
) -> None:
    """Replay discovers each matching domain once; later additions discover again."""
    with (
        patch(
            "homeassistant.components.lorawan.async_get_lorawan",
            return_value={
                "test_vendor": [("example", 123)],
                "other_vendor": [("example", 456)],
            },
        ),
        patch(
            "homeassistant.components.lorawan.connection.discovery_flow.async_create_flow"
        ) as discover,
    ):
        backend, _ = await registered_backend(
            "network",
            [
                DESCRIPTOR,
                replace(DESCRIPTOR, dev_eui="0201010101010102"),
                replace(DESCRIPTOR, dev_eui="0201010101010103", brand_id=456),
                replace(DESCRIPTOR, dev_eui="0201010101010104", brand_id=456),
            ],
        )
        assert [call.args[1] for call in discover.call_args_list] == [
            "other_vendor",
            "test_vendor",
        ]
        backend.emit(
            AddedEvent(
                descriptor=replace(
                    DESCRIPTOR, dev_eui="0201010101010105", brand_id=456
                ),
                received_at=dt_util.utcnow(),
            )
        )
        assert [call.args[1] for call in discover.call_args_list] == [
            "other_vendor",
            "test_vendor",
            "other_vendor",
        ]


async def test_duplicate_registration(
    hass: HomeAssistant, registered_backend: RegisterBackend
) -> None:
    """An active provider cannot be replaced without withdrawal."""
    backend, _ = await registered_backend("network", [DESCRIPTOR])
    entry = hass.config_entries.async_get_entry("network")
    with pytest.raises(ValueError, match="already registered"):
        await async_register_connection(
            hass, entry, connection=MockConnection(stack_type="example")
        )
    assert hass.data[DATA_REGISTRY].connections["network"].connection is backend


@pytest.mark.parametrize(
    "error", [ConnectionUnavailable("offline"), asyncio.CancelledError()]
)
async def test_registration_failure(
    hass: HomeAssistant, connection_entry: MockConfigEntry, error: BaseException
) -> None:
    """Failure and cancellation clean up discovery and allow a later attempt."""
    assert await async_setup_component(hass, "lorawan", {})
    stop_disconnect = Mock()
    backend = Mock(
        stack_type="example",
        on_disconnect=Mock(return_value=stop_disconnect),
        async_subscribe=AsyncMock(side_effect=error),
    )
    with pytest.raises(type(error)):
        await async_register_connection(hass, connection_entry, connection=backend)
    stop_disconnect.assert_called_once_with()
    assert not hass.data[DATA_REGISTRY].connections

    unsubscribe = await async_register_connection(
        hass, connection_entry, connection=MockConnection(stack_type="example")
    )
    unsubscribe()


async def test_concurrent_registration(
    hass: HomeAssistant, connection_entry: MockConfigEntry
) -> None:
    """The entry is reserved while existing devices are being replayed."""
    assert await async_setup_component(hass, "lorawan", {})
    started, finish = asyncio.Event(), asyncio.Event()
    stop_events, stop_disconnect = Mock(), Mock()

    async def replay(
        *,
        brands: frozenset[tuple[str, int | str]] | None,
        listener: Callable[[DeviceEvent], None],
    ) -> Mock:
        started.set()
        await finish.wait()
        return stop_events

    backend = Mock(
        stack_type="example",
        on_disconnect=Mock(return_value=stop_disconnect),
        async_subscribe=AsyncMock(side_effect=replay),
    )
    registration = hass.async_create_task(
        async_register_connection(hass, connection_entry, connection=backend)
    )
    await started.wait()
    with pytest.raises(ValueError, match="already registered"):
        await async_register_connection(
            hass, connection_entry, connection=MockConnection(stack_type="example")
        )
    finish.set()
    unsubscribe = await registration
    unsubscribe()
    stop_events.assert_called_once_with()
    stop_disconnect.assert_called_once_with()


async def test_disconnect_during_registration(
    hass: HomeAssistant, connection_entry: MockConfigEntry
) -> None:
    """A disconnect during replay cannot publish or discover a stale connection."""
    assert await async_setup_component(hass, "lorawan", {})
    stop_events, stop_disconnect = Mock(), Mock()
    backend = Mock(
        stack_type="example", on_disconnect=Mock(return_value=stop_disconnect)
    )

    async def replay(
        *,
        brands: frozenset[tuple[str, int | str]] | None,
        listener: Callable[[DeviceEvent], None],
    ) -> Mock:
        listener(AddedEvent(descriptor=DESCRIPTOR, received_at=dt_util.utcnow()))
        backend.on_disconnect.call_args.args[0]()
        return stop_events

    backend.async_subscribe = AsyncMock(side_effect=replay)
    with (
        patch(
            "homeassistant.components.lorawan.connection.discovery_flow.async_create_flow"
        ) as discover,
        pytest.raises(ConnectionUnavailable),
    ):
        await async_register_connection(hass, connection_entry, connection=backend)
    discover.assert_not_called()
    stop_events.assert_called_once_with()
    stop_disconnect.assert_called_once_with()
    assert not hass.data[DATA_REGISTRY].connections

    with patch(
        "homeassistant.components.lorawan.connection.discovery_flow.async_create_flow"
    ) as discover:
        unsubscribe = await async_register_connection(
            hass,
            connection_entry,
            connection=MockConnection([DESCRIPTOR], stack_type="example"),
        )
        discover.assert_called_once()
        unsubscribe()


async def test_shutdown_releases_subscriptions(
    hass: HomeAssistant, registered_backend: RegisterBackend
) -> None:
    """HA shutdown releases discovery without closing provider-owned transports."""
    backend, _ = await registered_backend("network", [DESCRIPTOR])
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert not hass.data[DATA_REGISTRY].connections
    with patch(
        "homeassistant.components.lorawan.connection.discovery_flow.async_create_flow"
    ) as discover:
        backend.emit(UpdatedEvent(descriptor=DESCRIPTOR, received_at=dt_util.utcnow()))
    discover.assert_not_called()


@pytest.mark.parametrize("stack_type", ["example", "other_stack"])
async def test_discovery_matches_connection_stack(
    hass: HomeAssistant, registered_backend: RegisterBackend, stack_type: str
) -> None:
    """Identical brand IDs in different catalogs discover only the matching stack."""
    with (
        patch(
            "homeassistant.components.lorawan.async_get_lorawan",
            return_value={
                "example": [("example", 123)],
                "other_stack": [("other_stack", 123)],
            },
        ),
        patch(
            "homeassistant.components.lorawan.connection.discovery_flow.async_create_flow"
        ) as discover,
        patch.object(
            MockConnection,
            "async_subscribe",
            autospec=True,
            side_effect=MockConnection.async_subscribe,
        ) as subscribe,
    ):
        backend, _ = await registered_backend(
            "network", [replace(DESCRIPTOR, stack=stack_type)]
        )
        assert backend.stack_type == stack_type
        assert subscribe.call_args.kwargs["brands"] is None
        discover.assert_called_once_with(
            hass,
            stack_type,
            context={"source": SOURCE_INTEGRATION_DISCOVERY},
            data=LoRaWANDiscoveryInfo(),
        )
