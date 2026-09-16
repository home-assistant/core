"""Test the Teslemetry repairs."""

import asyncio
from collections.abc import Generator
from copy import deepcopy
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientError
from aiohttp.test_utils import TestClient
from aiopowerwall import (
    PowerwallAuthenticationError,
    PowerwallConnectionError,
    PowerwallError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from tesla_fleet_api.exceptions import (
    BluetoothTimeout,
    InvalidResponse,
    NotOnWhitelistFault,
    PrivateKeyError,
    TeslaFleetError,
)
from tesla_fleet_api.tesla.bluetooth import TeslaBluetooth

from homeassistant.components.repairs import ConfirmRepairFlow
from homeassistant.components.teslemetry.const import (
    CONF_SITE_ID,
    DOMAIN,
    ISSUE_TYPE_BLE_KEY_REJECTED,
    RSA_PARENT_KEY,
    SUBENTRY_TYPE_ENERGY_SITE,
)
from homeassistant.components.teslemetry.coordinator import METADATA_INTERVAL
from homeassistant.components.teslemetry.repairs import async_create_fix_flow
from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.const import CONF_HOST, CONF_PASSWORD
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
        "homeassistant.components.teslemetry.pairing_flow.async_discovered_service_info",
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
        "homeassistant.components.teslemetry.pairing_flow.async_get_ble_parent",
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
