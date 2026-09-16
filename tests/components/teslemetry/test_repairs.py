"""Test the Teslemetry repairs."""

import asyncio
from collections.abc import Awaitable, Callable, Generator
from copy import deepcopy
from dataclasses import replace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

from aiohttp import ClientError
from aiohttp.test_utils import TestClient
from aiopowerwall import (
    PowerwallAuthenticationError,
    PowerwallConnectionError,
    PowerwallError,
)
from bleak.exc import BleakError
from freezegun.api import FrozenDateTimeFactory
import pytest
from tesla_fleet_api.exceptions import (
    BluetoothTimeout,
    BluetoothTransportError,
    InvalidResponse,
    NotOnWhitelistFault,
    PrivateKeyError,
    SessionInfoAuthenticationFault,
    TeslaFleetError,
    TeslaFleetMessageFaultBusy,
    TeslaFleetMessageFaultInternal,
    TeslaFleetMessageFaultKeychainIsFull,
    TeslaFleetMessageFaultTimeout,
    TeslaFleetMessageFaultUnknownKeyId,
)
from tesla_fleet_api.router import VehicleRouter
from tesla_fleet_api.tesla.bluetooth import TeslaBluetooth

from homeassistant.components.repairs import ConfirmRepairFlow, FlowType
from homeassistant.components.teslemetry.const import (
    CONF_SITE_ID,
    CONF_VIN,
    DOMAIN,
    ISSUE_TYPE_BLE_KEY_REJECTED,
    RSA_PARENT_KEY,
    SUBENTRY_TYPE_ENERGY_SITE,
    SUBENTRY_TYPE_VEHICLE,
)
from homeassistant.components.teslemetry.coordinator import METADATA_INTERVAL
from homeassistant.components.teslemetry.repairs import async_create_fix_flow
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntryState,
    ConfigSubentryData,
)
from homeassistant.const import CONF_ADDRESS, CONF_HOST, CONF_PASSWORD
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
SITE_ID = 123456
HOST = "192.168.91.1"
NEW_HOST = "192.168.91.2"
PASSWORD = "abcde"
GATEWAY_ISSUE_ID = f"gateway_not_found_{SITE_ID}"
FIND_GATEWAY_ADDRESS = (
    "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_gateway_address"
)


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

    # Teslemetry's cloud cannot handshake, but a signed cloud backend can, so give it one that succeeds.
    router.secondary.handshakeVehicleSecurity = AsyncMock(return_value=None)
    assert ir.async_get(hass).async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is not None
    return entry


async def _submit_ble_key_fix_flow(
    client: TestClient, flow_id: str, ble_device: MagicMock | None
) -> dict[str, Any]:
    """Submit the confirm step with the vehicle's Bluetooth lookup returning ble_device."""
    with patch(
        "homeassistant.components.teslemetry.async_ble_device_from_address",
        return_value=ble_device,
    ):
        return await process_repair_fix_flow(client, flow_id, json={})


async def _hang() -> None:
    """Never return, like a Bluetooth call to a vehicle that stops responding."""
    await asyncio.Event().wait()


async def _unload_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Unload the entry, and with it the vehicle's router."""
    with patch("homeassistant.components.teslemetry.PLATFORMS", []):
        assert await hass.config_entries.async_unload(entry.entry_id)


async def _drop_bluetooth_router(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Leave the vehicle on cloud control only, as when its Bluetooth key fails to load."""
    vehicle = entry.runtime_data.vehicles[0]
    vehicle.api = vehicle.api.secondary


@pytest.mark.usefixtures("enable_bluetooth")
async def test_ble_key_fix_flow_hands_off_to_reconfigure(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """The fix flow opens the rejecting vehicle's reconfigure flow, which clears it."""
    entry = await _raise_ble_key_issue(hass)
    router = entry.runtime_data.vehicles[0].api
    router.primary.handshakeVehicleSecurity.side_effect = NotOnWhitelistFault()
    subentry = next(
        subentry
        for subentry in entry.subentries.values()
        if subentry.unique_id == VEHICLE_VIN
    )
    client = await hass_client()

    result = await start_repair_fix_flow(client, DOMAIN, BLE_KEY_ISSUE_ID)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await _submit_ble_key_fix_flow(client, result["flow_id"], MagicMock())

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


@pytest.mark.parametrize(
    ("repair_scanners", "ble_device", "handshakes"),
    [
        pytest.param(0, None, 0, id="no_scanner"),
        # The scanner goes away before the reconfigure flow starts.
        pytest.param(1, MagicMock(), 1, id="reconfigure_aborts"),
    ],
)
async def test_ble_key_fix_flow_no_bluetooth(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    repair_scanners: int,
    ble_device: MagicMock | None,
    handshakes: int,
) -> None:
    """Without a connectable Bluetooth scanner the fix flow aborts and keeps the repair."""
    # No enable_bluetooth fixture here, so the reconfigure flow finds no scanner.
    entry = await _raise_ble_key_issue(hass)
    router = entry.runtime_data.vehicles[0].api
    router.primary.handshakeVehicleSecurity.side_effect = NotOnWhitelistFault()
    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, BLE_KEY_ISSUE_ID)

    with patch(
        "homeassistant.components.teslemetry.repairs.async_scanner_count",
        return_value=repair_scanners,
    ):
        result = await _submit_ble_key_fix_flow(client, result["flow_id"], ble_device)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "bluetooth_not_available"
    assert "next_flow" not in result
    assert router.primary.handshakeVehicleSecurity.await_count == handshakes
    assert not hass.config_entries.subentries.async_progress()
    assert issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is not None


@pytest.mark.usefixtures("enable_bluetooth")
async def test_ble_key_fix_flow_handshake_succeeds(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A key the vehicle accepts again over Bluetooth finishes the repair without re-pairing."""
    entry = await _raise_ble_key_issue(hass)
    router = entry.runtime_data.vehicles[0].api
    router.primary.handshakeVehicleSecurity.return_value = None
    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, BLE_KEY_ISSUE_ID)

    result = await _submit_ble_key_fix_flow(client, result["flow_id"], MagicMock())

    assert result["type"] == FlowResultType.CREATE_ENTRY
    router.primary.handshakeVehicleSecurity.assert_awaited_once_with()
    router.secondary.handshakeVehicleSecurity.assert_not_awaited()
    router.primary.disconnect.assert_not_awaited()
    assert not hass.config_entries.subentries.async_progress()
    assert issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is None


@pytest.mark.usefixtures("enable_bluetooth")
@pytest.mark.parametrize(
    "key_error",
    [
        pytest.param(NotOnWhitelistFault(), id="not_on_whitelist"),
        pytest.param(TeslaFleetMessageFaultUnknownKeyId(), id="unknown_key_id"),
    ],
)
async def test_ble_key_fix_flow_bypasses_cloud_failover(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    key_error: TeslaFleetError,
) -> None:
    """A cloud handshake that would succeed cannot clear a key the vehicle still rejects."""
    entry = await _raise_ble_key_issue(hass)
    router = entry.runtime_data.vehicles[0].api
    router.primary.handshakeVehicleSecurity.side_effect = key_error
    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, BLE_KEY_ISSUE_ID)

    result = await _submit_ble_key_fix_flow(client, result["flow_id"], MagicMock())

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure"
    assert result["next_flow"][0] == FlowType.CONFIG_SUBENTRIES_FLOW
    router.primary.handshakeVehicleSecurity.assert_awaited_once_with()
    router.secondary.handshakeVehicleSecurity.assert_not_awaited()
    assert issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is not None


@pytest.mark.usefixtures("enable_bluetooth")
@pytest.mark.parametrize(
    "disconnect_side_effect",
    [
        pytest.param(None, id="disconnected"),
        pytest.param(BleakError(), id="bleak_error"),
        pytest.param(BluetoothTransportError(), id="library_error"),
        pytest.param(_hang, id="hung"),
    ],
)
async def test_ble_key_fix_flow_disconnects_before_reconfigure(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    disconnect_side_effect: BaseException | Callable[[], Any] | None,
) -> None:
    """A rejected key releases the repair's Bluetooth link before the reconfigure flow opens its own."""
    entry = await _raise_ble_key_issue(hass)
    router = entry.runtime_data.vehicles[0].api
    router.primary.handshakeVehicleSecurity.side_effect = NotOnWhitelistFault()
    router.primary.disconnect.side_effect = disconnect_side_effect
    subentry = next(
        subentry
        for subentry in entry.subentries.values()
        if subentry.unique_id == VEHICLE_VIN
    )
    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, BLE_KEY_ISSUE_ID)

    # One parent records both calls, so their order can be asserted.
    calls = MagicMock()
    calls.attach_mock(router.primary.disconnect, "disconnect")
    with (
        patch.object(
            hass.config_entries.subentries,
            "async_init",
            wraps=hass.config_entries.subentries.async_init,
        ) as reconfigure,
        # Bound the hung disconnect without waiting out the real timeout.
        patch("homeassistant.components.teslemetry.repairs.BLE_DISCONNECT_TIMEOUT", 0),
    ):
        calls.attach_mock(reconfigure, "reconfigure")
        result = await _submit_ble_key_fix_flow(client, result["flow_id"], MagicMock())
    # The entry unload at teardown disconnects again, and must not hang.
    router.primary.disconnect.side_effect = None

    assert calls.mock_calls == [
        call.disconnect(),
        call.reconfigure(
            (entry.entry_id, SUBENTRY_TYPE_VEHICLE),
            context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry.subentry_id},
        ),
    ]
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure"
    assert result["next_flow"][0] == FlowType.CONFIG_SUBENTRIES_FLOW
    assert issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is not None


@pytest.mark.usefixtures("enable_bluetooth")
async def test_ble_key_fix_flow_checks_the_repaired_vehicle(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Another vehicle accepting its key cannot clear this vehicle's repair."""
    entry = await _raise_ble_key_issue(hass)
    vehicle = entry.runtime_data.vehicles[0]
    vehicle.api.primary.handshakeVehicleSecurity.side_effect = NotOnWhitelistFault()
    other_bluetooth_vehicle = AsyncMock()
    other_bluetooth_vehicle.handshakeVehicleSecurity.return_value = None
    # Listed first so the repair cannot find the right router by position.
    entry.runtime_data.vehicles.insert(
        0,
        replace(
            vehicle,
            vin=OTHER_VIN,
            api=VehicleRouter(other_bluetooth_vehicle, vehicle.api.secondary),
        ),
    )
    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, BLE_KEY_ISSUE_ID)

    result = await _submit_ble_key_fix_flow(client, result["flow_id"], MagicMock())

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure"
    vehicle.api.primary.handshakeVehicleSecurity.assert_awaited_once_with()
    other_bluetooth_vehicle.handshakeVehicleSecurity.assert_not_awaited()
    other_bluetooth_vehicle.disconnect.assert_not_awaited()
    assert issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is not None


@pytest.mark.usefixtures("enable_bluetooth")
@pytest.mark.parametrize(
    ("ble_device", "handshake_side_effect", "error", "handshakes"),
    [
        pytest.param(None, None, "cannot_connect", 0, id="out_of_range"),
        pytest.param(
            MagicMock(), BluetoothTransportError(), "cannot_connect", 1, id="transport"
        ),
        pytest.param(
            MagicMock(), BluetoothTimeout(), "cannot_connect", 1, id="bluetooth_timeout"
        ),
        pytest.param(MagicMock(), _hang, "cannot_connect", 1, id="hung"),
        pytest.param(
            MagicMock(), TeslaFleetMessageFaultBusy(), "cannot_connect", 1, id="busy"
        ),
        pytest.param(
            MagicMock(),
            TeslaFleetMessageFaultTimeout(),
            "cannot_connect",
            1,
            id="subsystem_timeout",
        ),
        pytest.param(
            MagicMock(),
            TeslaFleetMessageFaultInternal(),
            "cannot_connect",
            1,
            id="booting",
        ),
        pytest.param(
            MagicMock(),
            TeslaFleetMessageFaultKeychainIsFull(),
            "unknown",
            1,
            id="other_fault",
        ),
        pytest.param(
            MagicMock(),
            SessionInfoAuthenticationFault(),
            "unknown",
            1,
            id="session_info_unauthenticated",
        ),
    ],
)
async def test_ble_key_fix_flow_keeps_repair_open(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    ble_device: MagicMock | None,
    handshake_side_effect: BaseException | Callable[[], Any] | None,
    error: str,
    handshakes: int,
) -> None:
    """A handshake that cannot prove the key either way re-shows the form without re-pairing."""
    entry = await _raise_ble_key_issue(hass)
    router = entry.runtime_data.vehicles[0].api
    router.primary.handshakeVehicleSecurity.side_effect = handshake_side_effect
    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, BLE_KEY_ISSUE_ID)

    # Bound the hung handshake without waiting out the real timeout.
    with patch("homeassistant.components.teslemetry.repairs.BLE_HANDSHAKE_TIMEOUT", 0):
        result = await _submit_ble_key_fix_flow(client, result["flow_id"], ble_device)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": error}
    assert router.primary.handshakeVehicleSecurity.await_count == handshakes
    router.secondary.handshakeVehicleSecurity.assert_not_awaited()
    router.primary.disconnect.assert_not_awaited()
    assert not hass.config_entries.subentries.async_progress()
    assert issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is not None


@pytest.mark.usefixtures("enable_bluetooth")
@pytest.mark.parametrize(
    "remove_router",
    [
        pytest.param(_unload_entry, id="entry_unloaded"),
        pytest.param(_drop_bluetooth_router, id="cloud_only"),
    ],
)
async def test_ble_key_fix_flow_without_router(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    remove_router: Callable[[HomeAssistant, MockConfigEntry], Awaitable[None]],
) -> None:
    """Without a running Bluetooth router the fix flow aborts instead of guessing."""
    entry = await _raise_ble_key_issue(hass)
    bluetooth_vehicle = entry.runtime_data.vehicles[0].api.primary
    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, BLE_KEY_ISSUE_ID)
    await remove_router(hass, entry)

    result = await _submit_ble_key_fix_flow(client, result["flow_id"], MagicMock())

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "bluetooth_not_loaded"
    bluetooth_vehicle.handshakeVehicleSecurity.assert_not_awaited()
    assert not hass.config_entries.subentries.async_progress()


@pytest.fixture
def mock_powerwall_client() -> Generator[MagicMock]:
    """Mock the local Powerwall gateway client, starting unreachable."""
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.connect = AsyncMock(side_effect=PowerwallConnectionError("unreachable"))
    client.get_status = AsyncMock()
    with patch(
        "homeassistant.components.teslemetry.helpers.PowerwallClient",
        return_value=client,
    ):
        yield client


async def _setup_entry_with_lost_gateway(hass: HomeAssistant) -> MockConfigEntry:
    """Set up an entry whose paired gateway could not be found."""
    assert await async_setup_component(hass, "repairs", {})
    hass.data[RSA_PARENT_KEY] = b"test-key-pem"
    base = mock_config_entry()
    entry = MockConfigEntry(
        domain=base.domain,
        version=base.version,
        minor_version=base.minor_version,
        unique_id=base.unique_id,
        data=dict(base.data),
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_ENERGY_SITE,
                unique_id=str(SITE_ID),
                title="Energy Site",
                data={
                    CONF_SITE_ID: SITE_ID,
                    CONF_HOST: HOST,
                    CONF_PASSWORD: PASSWORD,
                },
            )
        ],
    )
    entry.add_to_hass(hass)
    with (
        patch(FIND_GATEWAY_ADDRESS, new=AsyncMock(return_value=None)),
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


def _host_default(result: dict[str, Any]) -> str:
    """Return the host field default from a serialized host form."""
    return next(
        field["default"]
        for field in result["data_schema"]
        if field["name"] == CONF_HOST
    )


async def test_gateway_repair_fixed_through_cloud(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    mock_powerwall_client: MagicMock,
) -> None:
    """The fix flow persists the address the cloud reports once it verifies."""
    entry = await _setup_entry_with_lost_gateway(hass)
    assert issue_registry.async_get_issue(DOMAIN, GATEWAY_ISSUE_ID) is not None
    client = await hass_client()

    mock_powerwall_client.connect.side_effect = None
    with (
        patch(FIND_GATEWAY_ADDRESS, new=AsyncMock(return_value=NEW_HOST)),
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
    ):
        result = await start_repair_fix_flow(client, DOMAIN, GATEWAY_ISSUE_ID)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    subentry = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0]
    assert subentry.data == {
        CONF_SITE_ID: SITE_ID,
        CONF_HOST: NEW_HOST,
        CONF_PASSWORD: PASSWORD,
    }
    mock_reload.assert_called_once_with(entry.entry_id)
    assert issue_registry.async_get_issue(DOMAIN, GATEWAY_ISSUE_ID) is None


@pytest.mark.parametrize(
    ("lookup_result", "expected_default", "lookup_errors"),
    [
        pytest.param([None], HOST, {}, id="no_address"),
        pytest.param(InvalidResponse(), HOST, {}, id="invalid_response"),
        pytest.param(ClientError(), HOST, {}, id="client_error"),
        pytest.param(
            [NEW_HOST],
            NEW_HOST,
            {"base": "cannot_connect"},
            id="new_address_unreachable",
        ),
    ],
)
@pytest.mark.parametrize(
    ("connect_error", "status_error", "error"),
    [
        pytest.param(
            PowerwallConnectionError("unreachable"),
            None,
            "cannot_connect",
            id="cannot_connect",
        ),
        pytest.param(
            PowerwallAuthenticationError("denied"),
            None,
            "invalid_auth",
            id="invalid_auth",
        ),
        pytest.param(
            None,
            PowerwallAuthenticationError("unapproved"),
            "key_not_approved",
            id="key_not_approved",
        ),
    ],
)
async def test_gateway_repair_manual_address(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    mock_powerwall_client: MagicMock,
    lookup_result: list[str | None] | Exception,
    expected_default: str,
    lookup_errors: dict[str, str],
    connect_error: PowerwallError | None,
    status_error: PowerwallError | None,
    error: str,
) -> None:
    """The fix flow asks for the address when the cloud lookup cannot fix it."""
    entry = await _setup_entry_with_lost_gateway(hass)
    client = await hass_client()

    with patch(FIND_GATEWAY_ADDRESS, new=AsyncMock(side_effect=lookup_result)):
        result = await start_repair_fix_flow(client, DOMAIN, GATEWAY_ISSUE_ID)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "host"
    assert result["description_placeholders"] == {"site": "Energy Site"}
    assert _host_default(result) == expected_default
    assert result["errors"] == lookup_errors

    mock_powerwall_client.connect.side_effect = connect_error
    mock_powerwall_client.get_status.side_effect = status_error
    result = await process_repair_fix_flow(
        client, result["flow_id"], json={CONF_HOST: "192.168.91.3"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert _host_default(result) == "192.168.91.3"

    mock_powerwall_client.connect.side_effect = None
    mock_powerwall_client.get_status.side_effect = None
    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        result = await process_repair_fix_flow(
            client, result["flow_id"], json={CONF_HOST: f" {NEW_HOST} "}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    subentry = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0]
    assert subentry.data[CONF_HOST] == NEW_HOST
    assert subentry.data[CONF_PASSWORD] == PASSWORD
    mock_reload.assert_called_once_with(entry.entry_id)
    assert issue_registry.async_get_issue(DOMAIN, GATEWAY_ISSUE_ID) is None


@pytest.mark.usefixtures("mock_powerwall_client")
async def test_gateway_repair_key_load_failure_aborts(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """The fix flow aborts when the RSA key cannot be loaded."""
    await _setup_entry_with_lost_gateway(hass)
    client = await hass_client()

    with patch(
        "homeassistant.components.teslemetry.repairs._async_get_rsa_key_pem",
        side_effect=PrivateKeyError("malformed", "Not a valid PEM private key"),
    ):
        result = await start_repair_fix_flow(client, DOMAIN, GATEWAY_ISSUE_ID)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    ("entry_id", "subentry_id"),
    [
        pytest.param("missing", None, id="missing_entry"),
        pytest.param(None, "missing", id="missing_subentry"),
    ],
)
@pytest.mark.usefixtures("mock_powerwall_client")
async def test_gateway_repair_aborts_without_loaded_site(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entry_id: str | None,
    subentry_id: str | None,
) -> None:
    """The fix flow aborts when its entry or site is no longer loaded."""
    entry = await _setup_entry_with_lost_gateway(hass)
    subentry = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0]
    ir.async_create_issue(
        hass,
        DOMAIN,
        "gateway_not_found_stale",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="gateway_not_found",
        translation_placeholders={"site": "Energy Site"},
        data={
            "entry_id": entry_id or entry.entry_id,
            "subentry_id": subentry_id or subentry.subentry_id,
        },
    )
    client = await hass_client()

    result = await start_repair_fix_flow(client, DOMAIN, "gateway_not_found_stale")

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"
