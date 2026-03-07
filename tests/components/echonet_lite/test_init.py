"""Tests for the ECHONET Lite initialization helpers."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import time
from unittest.mock import AsyncMock, patch

from pyhems import EOJ
from pyhems.runtime import HemsErrorEvent, HemsInstanceListEvent

from homeassistant.components.echonet_lite import async_setup, async_unload_entry
from homeassistant.components.echonet_lite.const import (
    CONF_ENABLE_EXPERIMENTAL,
    CONF_INTERFACE,
    DOMAIN,
    ISSUE_RUNTIME_CLIENT_ERROR,
    ISSUE_RUNTIME_INACTIVE,
    RUNTIME_MONITOR_MAX_SILENCE,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from .conftest import TestFrame, TestProperty, make_frame_event

from tests.common import MockConfigEntry


async def test_async_setup_creates_flow_when_missing_entry(hass: HomeAssistant) -> None:
    """Ensure async_setup starts an integration discovery flow."""

    with (
        patch.object(hass.config_entries, "async_entries", return_value=[]),
        patch.object(
            hass.config_entries.flow,
            "async_init",
            AsyncMock(),
        ) as mock_init,
    ):
        assert await async_setup(hass, {})
        await hass.async_block_till_done()

    mock_init.assert_awaited_once_with(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
    )


async def test_async_setup_skips_when_entry_exists(hass: HomeAssistant) -> None:
    """Ensure async_setup does nothing when an entry already exists."""

    with (
        patch.object(hass.config_entries, "async_entries", return_value=[object()]),
        patch.object(
            hass.config_entries.flow,
            "async_init",
            AsyncMock(),
        ) as mock_init,
    ):
        assert await async_setup(hass, {})
        await hass.async_block_till_done()

    mock_init.assert_not_called()


async def test_async_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_definitions_registry,
    mock_echonet_lite_client,
) -> None:
    """Test runtime data is stored and platforms unload cleanly."""

    entry = MockConfigEntry(domain=DOMAIN, options={CONF_INTERFACE: "192.168.1.100"})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.runtime_data.interface == "192.168.1.100"
    assert entry.runtime_data.definitions is not None
    assert entry.runtime_data.coordinator is not None
    assert entry.runtime_data.client is mock_echonet_lite_client
    assert entry.runtime_data.property_poller is not None
    mock_echonet_lite_client.start.assert_awaited_once()

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    mock_echonet_lite_client.stop.assert_awaited_once()


async def test_runtime_inactivity_issue_raised_and_cleared(
    hass: HomeAssistant,
    mock_definitions_registry,
    mock_echonet_lite_client,
) -> None:
    """Test that the runtime monitor raises and clears repair issues."""

    entry = MockConfigEntry(domain=DOMAIN, options={CONF_INTERFACE: "0.0.0.0"})
    entry.add_to_hass(hass)

    callbacks: list = []

    def _track_time_interval(
        hass: HomeAssistant,
        callback: Callable[[datetime], None],
        interval: timedelta,
    ) -> Callable[[], None]:
        callbacks.append(callback)
        return lambda: None

    with patch(
        "homeassistant.components.echonet_lite.async_track_time_interval",
        side_effect=_track_time_interval,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        issue_registry = ir.async_get(hass)

        monitor = entry.runtime_data.issue_monitor
        assert monitor is not None
        timeline = {"value": 0.0}
        monitor._monotonic = lambda: timeline["value"]
        monitor.record_activity(0.0)

        assert not issue_registry.async_get_issue(DOMAIN, ISSUE_RUNTIME_INACTIVE)

        timeline["value"] = RUNTIME_MONITOR_MAX_SILENCE.total_seconds() + 30
        assert callbacks
        callbacks[0](dt_util.utcnow())
        issue = issue_registry.async_get_issue(DOMAIN, ISSUE_RUNTIME_INACTIVE)
        assert issue is not None

        timeline["value"] = 0.0
        monitor.record_activity(0.0)
        assert not issue_registry.async_get_issue(DOMAIN, ISSUE_RUNTIME_INACTIVE)

        assert await async_unload_entry(hass, entry)


async def test_runtime_error_restart_success_updates_health(
    hass: HomeAssistant,
    mock_definitions_registry,
    mock_echonet_lite_client,
) -> None:
    """Test that runtime errors trigger a restart and update health metadata."""

    entry = MockConfigEntry(domain=DOMAIN, options={CONF_INTERFACE: "0.0.0.0"})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    error_event = HemsErrorEvent(received_at=1.0, error=RuntimeError("boom"))
    await mock_echonet_lite_client._listener(error_event)
    await hass.async_block_till_done()

    health = entry.runtime_data.health
    assert health is not None
    health = entry.runtime_data.health
    assert health is not None
    assert health.restart_attempts == 1
    assert health.last_client_error == "boom"
    assert health.last_client_error_at == 1.0
    assert health.last_restart_at is not None
    assert mock_echonet_lite_client.start.await_count == 2
    assert mock_echonet_lite_client.stop.await_count == 1

    issue_registry = ir.async_get(hass)
    assert not issue_registry.async_get_issue(DOMAIN, ISSUE_RUNTIME_CLIENT_ERROR)

    assert await async_unload_entry(hass, entry)


async def test_runtime_error_restart_failure_creates_issue(
    hass: HomeAssistant,
    mock_definitions_registry,
    mock_echonet_lite_client,
) -> None:
    """Test runtime errors raise a repair issue when restart fails."""

    mock_echonet_lite_client.start.side_effect = [None, OSError("socket busy")]

    entry = MockConfigEntry(domain=DOMAIN, options={CONF_INTERFACE: "0.0.0.0"})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    error_event = HemsErrorEvent(received_at=1.0, error=RuntimeError("boom"))
    await mock_echonet_lite_client._listener(error_event)
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_RUNTIME_CLIENT_ERROR)
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert "socket busy" in issue.translation_placeholders["error"]

    health = entry.runtime_data.health
    assert health is not None
    assert health.restart_attempts == 1
    assert health.last_restart_at is None

    assert mock_echonet_lite_client.start.await_count == 2
    assert mock_echonet_lite_client.stop.await_count == 1

    assert await async_unload_entry(hass, entry)


async def test_property_poller_requests_polled_properties(
    hass: HomeAssistant,
    mock_definitions_registry,
    mock_echonet_lite_client,
) -> None:
    """Ensure the property poller requests EPC values for new nodes."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_INTERFACE: "0.0.0.0", CONF_ENABLE_EXPERIMENTAL: True},
    )
    entry.add_to_hass(hass)

    callbacks: list = []

    def _track_time_interval(
        hass: HomeAssistant,
        callback: Callable[[datetime], None],
        interval: timedelta,
    ) -> Callable[[], None]:
        callbacks.append(callback)
        return lambda: None

    with patch(
        "homeassistant.components.echonet_lite.poller.async_track_time_interval",
        side_effect=_track_time_interval,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinator

    now = time.monotonic()
    node_id = bytes.fromhex("00000000000002").hex()
    node_profile_eoj = EOJ(0x0EF001)
    sensor_eoj = EOJ(0x001101)

    def _async_get(
        node_id_arg: str, eoj_arg: int, _epcs: list[int]
    ) -> list[TestProperty]:
        assert node_id_arg == node_id
        if eoj_arg == node_profile_eoj:
            return [
                TestProperty(epc=0x9F, edt=bytes.fromhex("018A")),
                TestProperty(epc=0x8A, edt=bytes.fromhex("000001")),
                TestProperty(epc=0xD6, edt=bytes.fromhex("01001101")),
            ]
        if eoj_arg == sensor_eoj:
            return [
                TestProperty(epc=0x9F, edt=bytes.fromhex("02E08A")),
                TestProperty(epc=0x9D, edt=bytes.fromhex("00")),
                TestProperty(epc=0x8A, edt=bytes.fromhex("000001")),
                TestProperty(epc=0xE0, edt=b"\x00d"),
            ]
        raise AssertionError(f"Unexpected EOJ {eoj_arg:06x}")

    mock_echonet_lite_client.async_get.side_effect = _async_get

    instance_event = HemsInstanceListEvent(
        received_at=now,
        instances=[node_profile_eoj, sensor_eoj],
        node_id=node_id,
        properties={},
    )

    await coordinator.async_process_instance_list_event(instance_event)
    await hass.async_block_till_done()

    # Verify nodes were created
    assert len(coordinator.data) == 2

    # The sensor node now has property maps; the poller should schedule polling
    assert callbacks
    prev_count = mock_echonet_lite_client.async_send.await_count
    callbacks[0](dt_util.utcnow())
    await hass.async_block_till_done()
    assert mock_echonet_lite_client.async_send.await_count > prev_count

    assert await async_unload_entry(hass, entry)


async def test_property_poller_falls_back_to_poll_when_notifications_disabled(
    hass: HomeAssistant,
    mock_definitions_registry,
    mock_echonet_lite_client,
) -> None:
    """Confirm the poller falls back to 0x62 when notifications are not supported."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_INTERFACE: "0.0.0.0", CONF_ENABLE_EXPERIMENTAL: True},
    )
    entry.add_to_hass(hass)

    callbacks: list = []

    def _track_time_interval(
        hass: HomeAssistant,
        callback: Callable[[datetime], None],
        interval: timedelta,
    ) -> Callable[[], None]:
        callbacks.append(callback)
        return lambda: None

    with patch(
        "homeassistant.components.echonet_lite.poller.async_track_time_interval",
        side_effect=_track_time_interval,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinator
    node_id = bytes.fromhex("00000000000002").hex()
    node_profile_eoj = EOJ(0x0EF001)
    sensor_eoj = EOJ(0x001101)

    def _async_get(
        node_id_arg: str, eoj_arg: int, _epcs: list[int]
    ) -> list[TestProperty]:
        assert node_id_arg == node_id
        if eoj_arg == node_profile_eoj:
            return [
                TestProperty(epc=0x9F, edt=bytes.fromhex("01D6")),
                TestProperty(epc=0xD6, edt=bytes.fromhex("01001101")),
                TestProperty(epc=0x8A, edt=bytes.fromhex("000001")),
            ]
        if eoj_arg == sensor_eoj:
            return [
                TestProperty(epc=0x9F, edt=bytes.fromhex("02E08A")),
                TestProperty(epc=0x9D, edt=bytes.fromhex("00")),
                TestProperty(epc=0x8A, edt=bytes.fromhex("000001")),
                TestProperty(epc=0xE0, edt=b"\x00d"),
            ]
        raise AssertionError(f"Unexpected EOJ {eoj_arg:06x}")

    mock_echonet_lite_client.async_get.side_effect = _async_get

    instance_event = HemsInstanceListEvent(
        received_at=30.0,
        instances=[node_profile_eoj, sensor_eoj],
        node_id=node_id,
        properties={},
    )

    await coordinator.async_process_instance_list_event(instance_event)
    await hass.async_block_till_done()

    assert len(coordinator.data) == 2

    # With notifications disabled, poller should still poll via 0x62
    assert callbacks
    callbacks[0](dt_util.utcnow())
    await hass.async_block_till_done()

    assert any(
        call.args[1].esv == 0x62
        and any(prop.epc == 0xE0 for prop in call.args[1].properties)
        for call in mock_echonet_lite_client.async_send.await_args_list
    )


async def test_node_created_with_property_maps(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test that nodes are created when property maps are received.

    This integration-level test ensures nodes are created when property maps are
    received, and subsequent frames update the existing node correctly.
    """

    entry = init_integration
    assert entry is not None

    coordinator = entry.runtime_data.coordinator
    node_hex = bytes.fromhex("00000000000001").hex()
    node_profile_eoj = EOJ(0x0EF001)
    sensor_eoj = EOJ(0x001101)

    def _async_get(
        node_id_arg: str, eoj_arg: int, _epcs: list[int]
    ) -> list[TestProperty]:
        assert node_id_arg == node_hex
        if eoj_arg == node_profile_eoj:
            return [
                TestProperty(epc=0x9F, edt=bytes.fromhex("028AD6")),
                TestProperty(epc=0x8A, edt=bytes.fromhex("000001")),
                TestProperty(epc=0xD6, edt=bytes.fromhex("01001101")),
            ]
        if eoj_arg == sensor_eoj:
            return [
                TestProperty(epc=0x9F, edt=bytes.fromhex("018A")),
                TestProperty(epc=0x8A, edt=bytes.fromhex("000001")),
            ]
        raise AssertionError(f"Unexpected EOJ {eoj_arg:06x}")

    entry.runtime_data.client.async_get.side_effect = _async_get

    with patch(
        "homeassistant.components.echonet_lite.coordinator.time.monotonic",
        side_effect=[30.0, 31.0],
    ):
        await coordinator._async_setup_device(node_hex, node_profile_eoj)
        await coordinator._async_setup_device(node_hex, sensor_eoj)

    # Parent node should be created
    parent_id = f"{node_hex}-{int(node_profile_eoj):06x}"
    assert parent_id in coordinator.data

    # Instance node should be created
    node_id = f"{node_hex}-{int(sensor_eoj):06x}"
    assert node_id in coordinator.data

    # Verify node state properties
    node_state = coordinator.data[node_id]
    assert node_state.get_epcs == frozenset({0x8A})  # From get map


async def test_node_updated_by_subsequent_frames(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test that existing nodes are updated by subsequent frames.

    This integration-level test ensures that when a node is created with property maps,
    subsequent frames update the existing node state correctly.
    """

    entry = init_integration
    assert entry is not None

    coordinator = entry.runtime_data.coordinator
    node_hex = bytes.fromhex("00000000000001").hex()
    node_profile_eoj = EOJ(0x0EF001)

    entry.runtime_data.client.async_get.return_value = [
        TestProperty(epc=0x9F, edt=bytes.fromhex("028AD6")),
        TestProperty(epc=0x8A, edt=bytes.fromhex("000001")),
    ]

    with patch(
        "homeassistant.components.echonet_lite.coordinator.time.monotonic",
        return_value=30.0,
    ):
        await coordinator._async_setup_device(node_hex, node_profile_eoj)

    # Node should be created
    node_id = f"{node_hex}-{int(node_profile_eoj):06x}"
    assert node_id in coordinator.data
    node_state = coordinator.data[node_id]
    assert node_state.manufacturer_code == 0x000001  # stored as int
    assert 0xD6 not in node_state.properties  # Not yet received

    # Frames no longer update existing nodes
    update_frame = TestFrame(
        tid=2,
        seoj=int(node_profile_eoj).to_bytes(3, "big"),
        deoj=bytes.fromhex("05ff01"),
        esv=0x72,
        properties=[
            TestProperty(epc=0xD6, edt=bytes.fromhex("01001101")),
        ],
    )
    await coordinator.async_process_frame_event(
        make_frame_event(
            update_frame,
            received_at=31.0,
            node_id=node_hex,
            eoj=node_profile_eoj,
        ),
    )
    await hass.async_block_till_done()

    node_state = coordinator.data[node_id]
    assert 0xD6 in node_state.properties
    assert node_state.properties[0xD6] == bytes.fromhex("01001101")


async def test_property_poller_respects_get_property_map(
    hass: HomeAssistant,
    mock_definitions_registry,
    mock_echonet_lite_client,
) -> None:
    """Ensure the poller only requests properties listed in the Get property map."""

    entry = MockConfigEntry(domain=DOMAIN, options={CONF_INTERFACE: "0.0.0.0"})
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.echonet_lite.poller.async_track_time_interval",
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinator
    now = time.monotonic()

    node_hex = bytes.fromhex("00000000000002").hex()

    entry.runtime_data.client.async_get.return_value = [
        TestProperty(epc=0x9F, edt=bytes.fromhex("018A")),  # Get map: 1 EPC (0x8A)
        TestProperty(epc=0x9D, edt=bytes.fromhex("00")),  # INF map: empty
        TestProperty(epc=0x8A, edt=bytes.fromhex("000001")),
    ]

    with patch(
        "homeassistant.components.echonet_lite.coordinator.time.monotonic",
        return_value=now,
    ):
        await coordinator._async_setup_device(node_hex, EOJ(0x001101))

    await hass.async_block_till_done()

    # Verify that NO requests were sent for 0xE0
    # Check all calls to async_send
    for call in mock_echonet_lite_client.async_send.call_args_list:
        frame = call.args[1]
        # Ensure 0xE0 is NOT in any request
        assert not any(p.epc == 0xE0 for p in frame.properties), (
            f"Found request for 0xE0 in {frame}"
        )

    assert await async_unload_entry(hass, entry)


async def test_property_poller_requests_notifications_for_required_epcs(
    hass: HomeAssistant,
    mock_definitions_registry,
    mock_echonet_lite_client,
) -> None:
    """Ensure the poller polls required EPCs not in INF map."""

    entry = MockConfigEntry(domain=DOMAIN, options={CONF_INTERFACE: "0.0.0.0"})
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.echonet_lite.poller.async_track_time_interval",
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinator
    now = time.monotonic()

    node_hex = bytes.fromhex("00000000000002").hex()

    entry.runtime_data.client.async_get.return_value = [
        # Get map: 0x8A (ID) and 0xB3 (required temp setpoint)
        TestProperty(epc=0x9F, edt=bytes.fromhex("028AB3")),
        # INF map announces 0xB3 so 0x63 can be used
        TestProperty(epc=0x9D, edt=bytes.fromhex("01B3")),
        TestProperty(epc=0x8A, edt=bytes.fromhex("000001")),
        TestProperty(epc=0xB3, edt=bytes.fromhex("19")),
    ]

    with patch(
        "homeassistant.components.echonet_lite.coordinator.time.monotonic",
        return_value=now,
    ):
        await coordinator._async_setup_device(node_hex, EOJ(0x013001))

    await hass.async_block_till_done()

    # Initial 0x63 should be sent once after device creation (since INF map includes 0xB3)
    calls = mock_echonet_lite_client.async_send.await_args_list
    assert any(
        call.args[1].esv == 0x63
        and any(prop.epc == 0xB3 for prop in call.args[1].properties)
        for call in calls
    ), "Should request notifications for 0xB3 via 0x63"


async def test_property_poller_handles_sna_notification_response(
    hass: HomeAssistant,
    mock_definitions_registry,
    mock_echonet_lite_client,
) -> None:
    """Ensure the poller keeps polling when device does not announce values."""

    entry = MockConfigEntry(domain=DOMAIN, options={CONF_INTERFACE: "0.0.0.0"})
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.echonet_lite.poller.async_track_time_interval",
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinator
    now = time.monotonic()

    node_hex = bytes.fromhex("00000000000002").hex()

    entry.runtime_data.client.async_get.return_value = [
        TestProperty(epc=0x9F, edt=bytes.fromhex("028AB3")),
        # INF map is empty: device does not announce B3
        TestProperty(epc=0x9D, edt=bytes.fromhex("00")),
        TestProperty(epc=0x8A, edt=bytes.fromhex("000001")),
        TestProperty(epc=0xB3, edt=bytes.fromhex("19")),
    ]

    with patch(
        "homeassistant.components.echonet_lite.coordinator.time.monotonic",
        return_value=now,
    ):
        await coordinator._async_setup_device(node_hex, EOJ(0x013001))

    await hass.async_block_till_done()

    # No 0x63 should be sent because INF map does not include 0xB3
    assert not any(
        call.args[1].esv == 0x63
        for call in mock_echonet_lite_client.async_send.await_args_list
    ), "Should not request notifications when device does not announce properties"

    # Trigger polling interval manually (async_track_time_interval is patched)
    entry.runtime_data.property_poller._async_handle_interval()
    await hass.async_block_till_done()

    # Should poll 0xB3
    assert any(
        call.args[1].esv == 0x62
        and any(prop.epc == 0xB3 for prop in call.args[1].properties)
        for call in mock_echonet_lite_client.async_send.await_args_list
    )
