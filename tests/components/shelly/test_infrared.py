"""Tests for the Shelly infrared platform."""

from unittest.mock import Mock

from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
from infrared_protocols.commands import Command as InfraredCommand
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    async_send_command,
)
from homeassistant.components.shelly.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_registry import EntityRegistry

from . import init_integration

ENTITY_ID = f"{INFRARED_DOMAIN}.test_name_infrared_emitter"


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


async def test_infrared_emitter(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    snapshot: SnapshotAssertion,
    entity_registry: EntityRegistry,
) -> None:
    """Test the infrared emitter entity."""
    await init_integration(hass, 4)

    assert (state := hass.states.get(ENTITY_ID))
    assert state == snapshot(name=f"{ENTITY_ID}-state")

    assert (entry := entity_registry.async_get(ENTITY_ID))
    assert entry == snapshot(name=f"{ENTITY_ID}-entry")


async def test_rpc_send_ir_command(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
) -> None:
    """Test RPC send IR command."""
    await init_integration(hass, 4)

    ir_command = MockIrCommand(
        modulation=38000, repeat_count=0, timings=[9000, -4500, 560, -1690]
    )
    await async_send_command(hass, ENTITY_ID, ir_command)

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

    ir_command = MockIrCommand(
        modulation=38000, repeat_count=0, timings=[9000, -4500, 560, -1690]
    )
    with pytest.raises(HomeAssistantError, match=error):
        await async_send_command(hass, ENTITY_ID, ir_command)


async def test_rpc_send_ir_command_reauth(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
) -> None:
    """Test RPC send IR command with authentication error."""
    entry = await init_integration(hass, 4)

    mock_rpc_device.ir_emit_raw.side_effect = InvalidAuthError

    ir_command = MockIrCommand(
        modulation=38000, repeat_count=0, timings=[9000, -4500, 560, -1690]
    )
    await async_send_command(hass, ENTITY_ID, ir_command)

    assert entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id
