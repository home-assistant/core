"""Tests for the Shelly infrared platform."""

from unittest.mock import Mock

from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
from infrared_protocols.commands import Command as InfraredCommand
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    InfraredReceivedSignal,
    async_send_command,
    async_subscribe_receiver,
)
from homeassistant.components.shelly.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_registry import EntityRegistry

from . import init_integration, inject_rpc_device_event

ENTITY_ID_EMITTER = f"{INFRARED_DOMAIN}.test_name_infrared_emitter"
ENTITY_ID_RECEIVER = f"{INFRARED_DOMAIN}.test_name_infrared_receiver"


class MockIrCommand(InfraredCommand):
    """Mock InfraredCommand."""

    def __init__(
        self,
        modulation: int,
        repeat_count: int,
        timings: list[int],
    ) -> None:
        """Initialize."""
        super().__init__(modulation=modulation, repeat_count=repeat_count)
        self._timings = timings

    def get_raw_timings(self) -> list[int]:
        """Return the configured timings."""
        return self._timings


IR_COMMAND = MockIrCommand(
    modulation=38000, repeat_count=0, timings=[9000, -4500, 560, -1690]
)


@pytest.mark.parametrize("entity_id", [ENTITY_ID_EMITTER, ENTITY_ID_RECEIVER])
async def test_infrared_entities(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    snapshot: SnapshotAssertion,
    entity_registry: EntityRegistry,
    entity_id: str,
) -> None:
    """Test the infrared entities."""
    await init_integration(hass, 4)

    assert (state := hass.states.get(entity_id))
    assert state == snapshot(name=f"{entity_id}-state")

    assert (entry := entity_registry.async_get(entity_id))
    assert entry == snapshot(name=f"{entity_id}-entry")


async def test_rpc_send_ir_command(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
) -> None:
    """Test RPC send IR command."""
    await init_integration(hass, 4)

    await async_send_command(hass, ENTITY_ID_EMITTER, IR_COMMAND)

    mock_rpc_device.ir_emit_raw.assert_awaited_once_with(
        [9000, -4500, 560, -1690],
        38000,
        0,
    )


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (
            DeviceConnectionError,
            "Device communication error occurred while calling action"
            " for infrared.test_name_infrared_emitter of Test name",
        ),
        (
            RpcCallError(999),
            "RPC call error occurred while calling action"
            " for infrared.test_name_infrared_emitter of Test name",
        ),
    ],
)
async def test_rpc_send_ir_command_exc(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    exception: Exception,
    error: str,
) -> None:
    """Test RPC."""
    await init_integration(hass, 4)

    mock_rpc_device.ir_emit_raw.side_effect = exception

    with pytest.raises(HomeAssistantError, match=error):
        await async_send_command(hass, ENTITY_ID_EMITTER, IR_COMMAND)


async def test_rpc_send_ir_command_reauth(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
) -> None:
    """Test RPC send IR command with authentication error."""
    entry = await init_integration(hass, 4)

    mock_rpc_device.ir_emit_raw.side_effect = InvalidAuthError

    await async_send_command(hass, ENTITY_ID_EMITTER, IR_COMMAND)

    assert entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


async def test_infrared_receiver_signal(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the infrared receiver entity receives a raw signal."""
    await init_integration(hass, 4)

    received_signals: list[InfraredReceivedSignal] = []
    async_subscribe_receiver(hass, ENTITY_ID_RECEIVER, received_signals.append)

    assert (state := hass.states.get(ENTITY_ID_RECEIVER))
    assert state.state == STATE_UNKNOWN

    timings = [1270, -410, 1280, -410, 450, -1230, 450, -1230, 450, -410]
    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {"events": [{"component": "ir", "event": "raw_receive", "timings": timings}]},
    )
    await hass.async_block_till_done()

    assert len(received_signals) == 1
    assert received_signals[0] == InfraredReceivedSignal(timings=timings)

    assert (state := hass.states.get(ENTITY_ID_RECEIVER))
    assert state.state != STATE_UNKNOWN


@pytest.mark.parametrize(
    "event",
    [
        {"events": [{"component": "ir", "event": "other_event", "timings": [100]}]},
        {"events": [{"component": "switch", "event": "raw_receive", "timings": [100]}]},
        {"events": [{"component": "ir", "event": "raw_receive", "timings": []}]},
        {"events": [{"component": "ir", "event": "raw_receive", "timings": None}]},
        {"events": [{"component": "ir", "event": "raw_receive"}]},
    ],
)
async def test_infrared_receiver_ignores_events(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    event: dict,
) -> None:
    """Test that irrelevant or empty events do not change the receiver state."""
    await init_integration(hass, 4)

    received_signals: list[InfraredReceivedSignal] = []
    async_subscribe_receiver(hass, ENTITY_ID_RECEIVER, received_signals.append)

    inject_rpc_device_event(monkeypatch, mock_rpc_device, event)
    await hass.async_block_till_done()

    assert received_signals == []
    assert (state := hass.states.get(ENTITY_ID_RECEIVER))
    assert state.state == STATE_UNKNOWN
