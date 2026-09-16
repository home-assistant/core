"""Test the Teslemetry repairs."""

from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from tesla_fleet_api.exceptions import NotOnWhitelistFault
from tesla_fleet_api.tesla.bluetooth import TeslaBluetooth

from homeassistant.components.repairs import ConfirmRepairFlow, FlowType
from homeassistant.components.teslemetry.const import (
    CONF_VIN,
    DOMAIN,
    ISSUE_TYPE_BLE_KEY_REJECTED,
    SUBENTRY_TYPE_VEHICLE,
)
from homeassistant.components.teslemetry.coordinator import METADATA_INTERVAL
from homeassistant.components.teslemetry.repairs import async_create_fix_flow
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntryState,
    ConfigSubentryData,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import mock_config_entry, setup_platform
from .const import METADATA

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator

VEHICLE_VIN = "LRW3F7EK4NC700000"
ADDRESS = "AA:BB:CC:DD:EE:FF"
OTHER_VIN = "LRW3F7EK4NC799999"
OTHER_ADDRESS = "11:22:33:44:55:66"
ENTRY_ID = "teslemetry_entry"
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
        {"issue_type": ISSUE_TYPE_BLE_KEY_REJECTED},
        {
            "issue_type": ISSUE_TYPE_BLE_KEY_REJECTED,
            "entry_id": "missing",
            "subentry_id": "missing",
        },
        {
            "issue_type": ISSUE_TYPE_BLE_KEY_REJECTED,
            "entry_id": ENTRY_ID,
            "subentry_id": "missing",
        },
    ],
)
async def test_repair_invalid_data_returns_confirm_flow(
    hass: HomeAssistant,
    data: dict[str, Any] | None,
) -> None:
    """Test invalid repair flow data falls back to a confirm flow."""
    MockConfigEntry(domain=DOMAIN, entry_id=ENTRY_ID).add_to_hass(hass)
    flow = await async_create_fix_flow(hass, "key_VIN", data)
    assert isinstance(flow, ConfirmRepairFlow)


def _entry_with_ble_vehicles() -> MockConfigEntry:
    """Return an entry with Bluetooth subentries for another vehicle and the account vehicle."""
    entry = mock_config_entry()
    return MockConfigEntry(
        domain=entry.domain,
        version=entry.version,
        minor_version=entry.minor_version,
        unique_id=entry.unique_id,
        data=dict(entry.data),
        subentries_data=[
            # Listed first so the repair cannot find the right vehicle by position.
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_VEHICLE,
                unique_id=OTHER_VIN,
                title="Other",
                data={CONF_VIN: OTHER_VIN, CONF_ADDRESS: OTHER_ADDRESS},
            ),
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_VEHICLE,
                unique_id=VEHICLE_VIN,
                title="Test",
                data={CONF_VIN: VEHICLE_VIN, CONF_ADDRESS: ADDRESS},
            ),
        ],
    )


async def _raise_ble_key_issue(hass: HomeAssistant) -> MockConfigEntry:
    """Set up Bluetooth vehicles and have the account vehicle reject the key."""
    assert await async_setup_component(hass, "repairs", {})
    entry = _entry_with_ble_vehicles()
    entry.add_to_hass(hass)
    bluetooth_vehicle = AsyncMock()
    bluetooth_vehicle.set_device = MagicMock()
    bluetooth_vehicle.flash_lights.side_effect = NotOnWhitelistFault()

    # TeslaBluetooth is mocked so no vehicle key file is written.
    with (
        patch(
            "homeassistant.components.teslemetry.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.teslemetry.helpers.TeslaBluetooth"
        ) as mock_parent,
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        mock_parent.return_value.get_private_key = AsyncMock()
        mock_parent.return_value.vehicles.createBluetooth.return_value = (
            bluetooth_vehicle
        )
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        router = entry.runtime_data.vehicles[0].api
        router.secondary.flash_lights = AsyncMock()
        await router.flash_lights()

    assert ir.async_get(hass).async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is not None
    return entry


@pytest.mark.usefixtures("enable_bluetooth")
async def test_ble_key_fix_flow_hands_off_to_reconfigure(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """The fix flow opens the rejecting vehicle's reconfigure flow, which clears it."""
    entry = await _raise_ble_key_issue(hass)
    subentry = next(
        subentry
        for subentry in entry.subentries.values()
        if subentry.unique_id == VEHICLE_VIN
    )
    client = await hass_client()

    result = await start_repair_fix_flow(client, DOMAIN, BLE_KEY_ISSUE_ID)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await process_repair_fix_flow(client, result["flow_id"], json={})

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure"
    assert result["result"]["entry_id"] == entry.entry_id
    flow_type, flow_id = result["next_flow"]
    assert flow_type == FlowType.CONFIG_SUBENTRIES_FLOW
    assert hass.config_entries.subentries.async_get(flow_id) == {
        "flow_id": flow_id,
        "handler": (entry.entry_id, SUBENTRY_TYPE_VEHICLE),
        "context": {"source": SOURCE_RECONFIGURE, "subentry_id": subentry.subentry_id},
        "step_id": "scan",
    }
    # Handing off does not resolve the repair; the key is still rejected.
    assert issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is not None

    info = MagicMock()
    info.name = TeslaBluetooth().get_name(VEHICLE_VIN)
    info.address = ADDRESS
    parent = MagicMock()
    parent.get_name.return_value = info.name
    parent.vehicles.createBluetooth.return_value = AsyncMock()
    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
            return_value=[info],
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.async_get_ble_parent",
            return_value=parent,
        ),
        patch(
            "homeassistant.components.teslemetry.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        result = await hass.config_entries.subentries.async_configure(flow_id, {})
        # The reconfigure schedules a reload, which unloads the router that raised the repair.
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    parent.vehicles.createBluetooth.assert_called_once_with(
        VEHICLE_VIN, device=info.device
    )
    assert entry.state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is None


async def test_ble_key_fix_flow_no_bluetooth(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Without a connectable Bluetooth scanner the fix flow aborts and keeps the repair."""
    # No enable_bluetooth fixture here, so the reconfigure flow finds no scanner.
    await _raise_ble_key_issue(hass)
    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, BLE_KEY_ISSUE_ID)

    result = await process_repair_fix_flow(client, result["flow_id"], json={})

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "bluetooth_not_available"
    assert "next_flow" not in result
    assert not hass.config_entries.subentries.async_progress()
    assert issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is not None
