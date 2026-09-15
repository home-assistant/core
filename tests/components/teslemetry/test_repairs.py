"""Test the Teslemetry repairs."""

import asyncio
from collections.abc import Generator
from copy import deepcopy
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp.test_utils import TestClient
from freezegun.api import FrozenDateTimeFactory
import pytest
from tesla_fleet_api.exceptions import (
    BluetoothTimeout,
    NotOnWhitelistFault,
    TeslaFleetError,
)
from tesla_fleet_api.tesla.bluetooth import TeslaBluetooth

from homeassistant.components.repairs import ConfirmRepairFlow
from homeassistant.components.teslemetry.const import (
    DOMAIN,
    ISSUE_TYPE_BLE_KEY_REJECTED,
)
from homeassistant.components.teslemetry.coordinator import METADATA_INTERVAL
from homeassistant.components.teslemetry.repairs import async_create_fix_flow
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import setup_platform
from .const import METADATA

from tests.common import async_fire_time_changed
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator

VEHICLE_VIN = "LRW3F7EK4NC700000"
BLE_KEY_ISSUE_ID = f"{ISSUE_TYPE_BLE_KEY_REJECTED}_{VEHICLE_VIN}"


def _metadata_with_issue(issue: str | None) -> dict[str, Any]:
    """Return a copy of the metadata with the vehicle issue set."""
    metadata = deepcopy(METADATA)
    metadata["vehicles"][VEHICLE_VIN]["issue"] = issue
    return metadata


def _metadata_without_vehicle() -> dict[str, Any]:
    """Return a copy of the metadata without the vehicle."""
    metadata = deepcopy(METADATA)
    del metadata["vehicles"][VEHICLE_VIN]
    return metadata


def _metadata_with_vehicle_access(access: bool) -> dict[str, Any]:
    """Return a copy of the metadata with the vehicle access set."""
    metadata = _metadata_with_issue("key")
    metadata["vehicles"][VEHICLE_VIN]["access"] = access
    return metadata


@pytest.mark.parametrize("issue_type", ["key", "streaming_toggle"])
async def test_repair_issue_created(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    issue_type: str,
) -> None:
    """Test a repair issue is created for an unresolved vehicle metadata issue."""
    with patch(
        "tesla_fleet_api.teslemetry.Teslemetry.metadata",
        return_value=_metadata_with_issue(issue_type),
    ):
        entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED

    issue = issue_registry.async_get_issue(DOMAIN, f"{issue_type}_{VEHICLE_VIN}")
    assert issue is not None
    assert issue.translation_key == issue_type
    assert issue.data == {
        "entry_id": entry.entry_id,
        "vin": VEHICLE_VIN,
        "issue_type": issue_type,
        "vehicle": "Home Assistant",
    }


@pytest.mark.parametrize("issue", [None, "no_data"])
async def test_no_repair_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    issue: str | None,
) -> None:
    """Test no repair issue is created when there is no actionable issue."""
    with patch(
        "tesla_fleet_api.teslemetry.Teslemetry.metadata",
        return_value=_metadata_with_issue(issue),
    ):
        entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED

    assert issue_registry.async_get_issue(DOMAIN, f"key_{VEHICLE_VIN}") is None
    assert (
        issue_registry.async_get_issue(DOMAIN, f"streaming_toggle_{VEHICLE_VIN}")
        is None
    )


async def test_repair_issue_auto_resolves(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a repair issue is removed once the metadata issue clears."""
    with patch(
        "tesla_fleet_api.teslemetry.Teslemetry.metadata",
        return_value=_metadata_with_issue("key"),
    ):
        entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, f"key_{VEHICLE_VIN}") is not None

    with patch(
        "tesla_fleet_api.teslemetry.Teslemetry.metadata",
        return_value=_metadata_with_issue(None),
    ):
        freezer.tick(METADATA_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, f"key_{VEHICLE_VIN}") is None


@pytest.mark.parametrize(
    "metadata",
    [
        pytest.param(_metadata_without_vehicle(), id="removed"),
        pytest.param(
            _metadata_with_vehicle_access(False),
            id="access_revoked",
        ),
    ],
)
async def test_repair_issue_removed_when_vehicle_no_longer_available(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
    metadata: dict[str, Any],
) -> None:
    """Test a repair issue is removed once the vehicle is no longer available."""
    with patch(
        "tesla_fleet_api.teslemetry.Teslemetry.metadata",
        return_value=_metadata_with_issue("key"),
    ):
        entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, f"key_{VEHICLE_VIN}") is not None

    with patch(
        "tesla_fleet_api.teslemetry.Teslemetry.metadata",
        return_value=metadata,
    ):
        freezer.tick(METADATA_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, f"key_{VEHICLE_VIN}") is None


async def test_repair_fix_flow(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the fix flow re-checks metadata and resolves once fixed."""
    assert await async_setup_component(hass, "repairs", {})
    client = await hass_client()

    with patch(
        "tesla_fleet_api.teslemetry.Teslemetry.metadata",
        return_value=_metadata_with_issue("key"),
    ):
        entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED

    issue_id = f"key_{VEHICLE_VIN}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    result = await start_repair_fix_flow(client, DOMAIN, issue_id)
    flow_id = result["flow_id"]
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    # Submitting while the key is still unpaired keeps the form open
    with patch(
        "tesla_fleet_api.teslemetry.Teslemetry.metadata",
        return_value=_metadata_with_issue("key"),
    ):
        result = await process_repair_fix_flow(client, flow_id, json={})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": "not_resolved"}
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    # Once the key is paired, re-checking resolves the issue
    with patch(
        "tesla_fleet_api.teslemetry.Teslemetry.metadata",
        return_value=_metadata_with_issue(None),
    ):
        result = await process_repair_fix_flow(client, flow_id, json={})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.parametrize(
    "data",
    [
        None,
        {"entry_id": "missing"},
        {"entry_id": 123, "vin": VEHICLE_VIN, "issue_type": "key", "vehicle": "Car"},
    ],
)
async def test_repair_invalid_data_returns_confirm_flow(
    hass: HomeAssistant,
    data: dict[str, Any] | None,
) -> None:
    """Test invalid repair flow data falls back to a confirm flow."""
    flow = await async_create_fix_flow(hass, "key_VIN", data)
    assert isinstance(flow, ConfirmRepairFlow)


@pytest.fixture
def ble_vehicle() -> AsyncMock:
    """Return a Bluetooth vehicle whose key is not yet whitelisted."""
    vehicle = AsyncMock()
    vehicle.handshakeVehicleSecurity = AsyncMock(
        side_effect=[NotOnWhitelistFault(), None]
    )
    return vehicle


@pytest.fixture
def discovered() -> Generator[MagicMock]:
    """Report the vehicle as discovered over Bluetooth."""
    info = MagicMock()
    info.name = TeslaBluetooth().get_name(VEHICLE_VIN)
    with patch(
        "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
        return_value=[info],
    ) as mock_discovered:
        yield mock_discovered


@pytest.fixture
def ble_parent(ble_vehicle: AsyncMock) -> Generator[MagicMock]:
    """Hand the fix flow the mock Bluetooth vehicle."""
    parent = MagicMock()
    parent.get_name.return_value = TeslaBluetooth().get_name(VEHICLE_VIN)
    parent.vehicles.createBluetooth.return_value = ble_vehicle
    with patch(
        "homeassistant.components.teslemetry.config_flow.async_get_ble_parent",
        return_value=parent,
    ):
        yield parent


async def _raise_ble_key_issue(hass: HomeAssistant) -> None:
    """Raise the Bluetooth key repair as the vehicle router does."""
    assert await async_setup_component(hass, "repairs", {})
    await setup_platform(hass, [])
    ir.async_create_issue(
        hass,
        DOMAIN,
        BLE_KEY_ISSUE_ID,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_TYPE_BLE_KEY_REJECTED,
        translation_placeholders={"vehicle": "Test"},
        data={"issue_type": ISSUE_TYPE_BLE_KEY_REJECTED, "vin": VEHICLE_VIN},
    )


async def _start_ble_key_fix_flow(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> tuple[TestClient, dict[str, Any]]:
    """Raise the Bluetooth key repair and open its fix flow at the scan step."""
    await _raise_ble_key_issue(hass)
    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, BLE_KEY_ISSUE_ID)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "scan"
    return client, result


async def _resume_fix_flow(client: TestClient, flow_id: str) -> dict[str, Any]:
    """Fetch the flow after its progress task finishes, as the frontend does."""
    resp = await client.get(f"/api/repairs/issues/fix/{flow_id}")
    assert resp.status == HTTPStatus.OK
    return await resp.json()


@pytest.mark.usefixtures("enable_bluetooth", "discovered", "ble_parent")
async def test_ble_key_fix_flow_re_pairs(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    ble_vehicle: AsyncMock,
) -> None:
    """The fix flow re-pairs the key on the vehicle and then clears the repair."""
    release = asyncio.Event()

    async def _pair() -> None:
        await release.wait()

    ble_vehicle.pair = AsyncMock(side_effect=_pair)
    client, result = await _start_ble_key_fix_flow(hass, hass_client)
    flow_id = result["flow_id"]

    result = await process_repair_fix_flow(client, flow_id, json={})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "instructions"

    result = await process_repair_fix_flow(client, flow_id, json={})
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "pair"
    # The repair stays open while the owner approves the key on the vehicle.
    assert issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is not None

    release.set()
    await hass.async_block_till_done()
    result = await _resume_fix_flow(client, flow_id)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is None
    ble_vehicle.connect.assert_awaited_once()
    ble_vehicle.pair.assert_awaited_once()
    ble_vehicle.disconnect.assert_awaited_once()


@pytest.mark.usefixtures("enable_bluetooth", "discovered", "ble_parent")
async def test_ble_key_fix_flow_already_whitelisted(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    ble_vehicle: AsyncMock,
) -> None:
    """A key the vehicle already accepts clears the repair without re-pairing."""
    ble_vehicle.handshakeVehicleSecurity = AsyncMock()
    client, result = await _start_ble_key_fix_flow(hass, hass_client)

    result = await process_repair_fix_flow(client, result["flow_id"], json={})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is None
    ble_vehicle.pair.assert_not_awaited()


@pytest.mark.usefixtures("enable_bluetooth", "ble_parent")
async def test_ble_key_fix_flow_device_not_found(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    discovered: MagicMock,
    ble_vehicle: AsyncMock,
) -> None:
    """A vehicle out of Bluetooth range keeps the repair open and can be retried."""
    ble_vehicle.handshakeVehicleSecurity = AsyncMock()
    found = discovered.return_value
    discovered.return_value = []
    client, result = await _start_ble_key_fix_flow(hass, hass_client)
    flow_id = result["flow_id"]

    result = await process_repair_fix_flow(client, flow_id, json={})

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "scan"
    assert result["errors"] == {"base": "device_not_found"}
    assert issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is not None
    ble_vehicle.connect.assert_not_awaited()

    discovered.return_value = found
    result = await process_repair_fix_flow(client, flow_id, json={})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is None


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(BluetoothTimeout(), "timeout", id="timeout"),
        pytest.param(TeslaFleetError(), "pair_failed", id="rejected"),
    ],
)
@pytest.mark.usefixtures("enable_bluetooth", "discovered", "ble_parent")
async def test_ble_key_fix_flow_pair_failure(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    ble_vehicle: AsyncMock,
    error: Exception,
    expected: str,
) -> None:
    """A failed re-pair keeps the repair open and the owner can approve again."""
    release = asyncio.Event()

    async def _pair() -> None:
        await release.wait()
        raise error

    ble_vehicle.pair = AsyncMock(side_effect=_pair)
    client, result = await _start_ble_key_fix_flow(hass, hass_client)
    flow_id = result["flow_id"]

    result = await process_repair_fix_flow(client, flow_id, json={})
    assert result["step_id"] == "instructions"
    result = await process_repair_fix_flow(client, flow_id, json={})
    assert result["type"] == FlowResultType.SHOW_PROGRESS

    release.set()
    await hass.async_block_till_done()
    result = await _resume_fix_flow(client, flow_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "instructions"
    assert result["errors"] == {"base": expected}
    assert issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is not None

    ble_vehicle.pair.side_effect = None
    result = await process_repair_fix_flow(client, flow_id, json={})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is None
    assert ble_vehicle.pair.await_count == 2


async def test_ble_key_fix_flow_no_bluetooth(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Without a connectable Bluetooth scanner the fix flow aborts and keeps the repair."""
    await _raise_ble_key_issue(hass)
    client = await hass_client()

    with patch(
        "homeassistant.components.teslemetry.repairs.async_scanner_count",
        return_value=0,
    ):
        result = await start_repair_fix_flow(client, DOMAIN, BLE_KEY_ISSUE_ID)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "bluetooth_not_available"
    assert issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is not None
