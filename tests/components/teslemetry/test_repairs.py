"""Test the Teslemetry repairs."""

import asyncio
from collections.abc import Awaitable, Callable, Generator
from copy import deepcopy
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
    BluetoothCommandFailed,
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
from tesla_fleet_api.tesla.bluetooth import TeslaBluetooth

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
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
    ConfigSubentry,
    ConfigSubentryData,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ADDRESS,
    CONF_HOST,
    CONF_PASSWORD,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import mock_config_entry, setup_platform
from .const import COMMAND_OK, METADATA, PRODUCTS

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator

VEHICLE_VIN = "LRW3F7EK4NC700000"
ADDRESS = "AA:BB:CC:DD:EE:FF"
OTHER_VIN = "LRW3F7EK4NC799999"
OTHER_ADDRESS = "11:22:33:44:55:66"
BLE_KEY_ISSUE_ID = f"{ISSUE_TYPE_BLE_KEY_REJECTED}_{VEHICLE_VIN}"
FLASH_LIGHTS_ENTITY_ID = "button.test_flash_lights"
UNNAMED_FLASH_LIGHTS_ENTITY_ID = "button.flash_lights"
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
            "entry_id": "entry",
            "subentry_id": 123,
        },
    ],
)
async def test_repair_invalid_data_returns_confirm_flow(
    hass: HomeAssistant,
    data: dict[str, Any] | None,
) -> None:
    """Test invalid repair flow data falls back to a confirm flow."""
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


def _vehicle_subentry(entry: MockConfigEntry) -> ConfigSubentry:
    """Return the account vehicle's Bluetooth subentry."""
    return next(
        subentry
        for subentry in entry.subentries.values()
        if subentry.unique_id == VEHICLE_VIN
    )


async def _setup_ble_vehicles(
    hass: HomeAssistant, entry: MockConfigEntry
) -> dict[str, AsyncMock]:
    """Set up the entry's Bluetooth vehicles, returning each vehicle's Bluetooth backend."""
    assert await async_setup_component(hass, "repairs", {})
    entry.add_to_hass(hass)
    bluetooth_vehicles: dict[str, AsyncMock] = {}

    def _create_bluetooth(vin: str, **kwargs: str | None) -> AsyncMock:
        bluetooth_vehicle = bluetooth_vehicles[vin] = AsyncMock()
        bluetooth_vehicle.set_device = MagicMock()
        return bluetooth_vehicle

    # TeslaBluetooth is mocked so no vehicle key file is written.
    with (
        patch(
            "homeassistant.components.teslemetry.helpers.TeslaBluetooth"
        ) as mock_parent,
        patch("homeassistant.components.teslemetry.PLATFORMS", [Platform.BUTTON]),
    ):
        mock_parent.return_value.get_private_key = AsyncMock()
        mock_parent.return_value.vehicles.createBluetooth.side_effect = (
            _create_bluetooth
        )
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return bluetooth_vehicles


async def _press_flash_lights(
    hass: HomeAssistant,
    ble_device: MagicMock | None,
    entity_id: str = FLASH_LIGHTS_ENTITY_ID,
) -> None:
    """Send a vehicle command with the vehicle's Bluetooth lookup returning ble_device."""
    with patch(
        "homeassistant.components.teslemetry.async_ble_device_from_address",
        return_value=ble_device,
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


async def _raise_ble_key_issue(
    hass: HomeAssistant,
) -> tuple[MockConfigEntry, dict[str, AsyncMock]]:
    """Set up Bluetooth vehicles and have the account vehicle reject the key."""
    entry = _entry_with_ble_vehicles()
    bluetooth_vehicles = await _setup_ble_vehicles(hass, entry)
    bluetooth_vehicles[VEHICLE_VIN].flash_lights.side_effect = NotOnWhitelistFault()

    await _press_flash_lights(hass, MagicMock())

    assert ir.async_get(hass).async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is not None
    return entry, bluetooth_vehicles


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


@pytest.mark.parametrize(
    ("key_error", "display_name", "entity_id", "vehicle"),
    [
        pytest.param(
            NotOnWhitelistFault(),
            "Test",
            FLASH_LIGHTS_ENTITY_ID,
            "Test",
            id="not_on_whitelist",
        ),
        pytest.param(
            TeslaFleetMessageFaultUnknownKeyId(),
            "Test",
            FLASH_LIGHTS_ENTITY_ID,
            "Test",
            id="unknown_key_id",
        ),
        pytest.param(
            NotOnWhitelistFault(),
            None,
            UNNAMED_FLASH_LIGHTS_ENTITY_ID,
            VEHICLE_VIN,
            id="unnamed_vehicle",
        ),
    ],
)
async def test_ble_key_rejected_raises_repair(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_products: MagicMock,
    key_error: TeslaFleetError,
    display_name: str | None,
    entity_id: str,
    vehicle: str,
) -> None:
    """A key rejection over Bluetooth raises a repair and the command still reaches the cloud."""
    products = deepcopy(PRODUCTS)
    products["response"][0]["display_name"] = display_name
    mock_products.return_value = products
    entry = _entry_with_ble_vehicles()
    bluetooth_vehicles = await _setup_ble_vehicles(hass, entry)
    bluetooth_vehicles[VEHICLE_VIN].flash_lights.side_effect = key_error

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.flash_lights", return_value=COMMAND_OK
    ) as cloud:
        await _press_flash_lights(hass, MagicMock(), entity_id)

    cloud.assert_awaited_once()
    # The cloud succeeding in the same call must not clear the repair.
    issue = issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID)
    assert issue is not None
    assert issue.translation_key == ISSUE_TYPE_BLE_KEY_REJECTED
    assert issue.translation_placeholders == {"vehicle": vehicle}
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.is_fixable
    assert issue.data == {
        "issue_type": ISSUE_TYPE_BLE_KEY_REJECTED,
        "entry_id": entry.entry_id,
        "subentry_id": _vehicle_subentry(entry).subentry_id,
    }


async def test_ble_key_rejected_repair_clears_on_bluetooth_success(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """A later command succeeding over Bluetooth clears the repair."""
    _, bluetooth_vehicles = await _raise_ble_key_issue(hass)
    bluetooth_vehicle = bluetooth_vehicles[VEHICLE_VIN]
    bluetooth_vehicle.flash_lights.side_effect = None
    bluetooth_vehicle.flash_lights.return_value = COMMAND_OK

    with patch("tesla_fleet_api.teslemetry.Vehicle.flash_lights") as cloud:
        await _press_flash_lights(hass, MagicMock())

    cloud.assert_not_awaited()
    assert issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is None


@pytest.mark.parametrize(
    "ble_error",
    [
        pytest.param(BluetoothTimeout(), id="timeout"),
        pytest.param(BluetoothTransportError(), id="transport"),
        pytest.param(BluetoothCommandFailed(), id="command_failed"),
        pytest.param(TeslaFleetMessageFaultKeychainIsFull(), id="keychain_full"),
        pytest.param(BleakError("no route"), id="bleak"),
        pytest.param(ValueError("unexpected"), id="unexpected"),
    ],
)
async def test_ble_non_key_failure_raises_no_repair(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, ble_error: Exception
) -> None:
    """A Bluetooth failure that is not a key rejection fails over without a repair."""
    bluetooth_vehicles = await _setup_ble_vehicles(hass, _entry_with_ble_vehicles())
    bluetooth_vehicles[VEHICLE_VIN].flash_lights.side_effect = ble_error

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.flash_lights", return_value=COMMAND_OK
    ) as cloud:
        await _press_flash_lights(hass, MagicMock())

    cloud.assert_awaited_once()
    assert issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is None


async def test_ble_key_rejected_ignores_cloud_rejection(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """A key rejection from the cloud is not a Bluetooth key rejection."""
    bluetooth_vehicles = await _setup_ble_vehicles(hass, _entry_with_ble_vehicles())

    with (
        patch(
            "tesla_fleet_api.teslemetry.Vehicle.flash_lights",
            side_effect=NotOnWhitelistFault(),
        ),
        pytest.raises(HomeAssistantError),
    ):
        # Out of Bluetooth range, so only the cloud is asked.
        await _press_flash_lights(hass, None)

    bluetooth_vehicles[VEHICLE_VIN].flash_lights.assert_not_awaited()
    assert issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is None


async def test_ble_key_rejected_repair_clears_on_unload(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Unloading the entry clears the repair along with the router that raised it."""
    entry, _ = await _raise_ble_key_issue(hass)

    with patch("homeassistant.components.teslemetry.PLATFORMS", [Platform.BUTTON]):
        assert await hass.config_entries.async_unload(entry.entry_id)

    assert issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is None


@pytest.mark.usefixtures("enable_bluetooth")
async def test_ble_key_fix_flow_hands_off_to_reconfigure(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """The fix flow opens the rejecting vehicle's reconfigure flow, which clears it."""
    entry, bluetooth_vehicles = await _raise_ble_key_issue(hass)
    bluetooth_vehicle = bluetooth_vehicles[VEHICLE_VIN]
    bluetooth_vehicle.handshakeVehicleSecurity.side_effect = NotOnWhitelistFault()
    subentry = _vehicle_subentry(entry)
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
    # The reconfigure flow's own link sees the key rejected, then approved with the key card.
    reconfigure_vehicle = AsyncMock()
    reconfigure_vehicle.handshakeVehicleSecurity.side_effect = [
        NotOnWhitelistFault(),
        None,
    ]
    key_card_tapped = asyncio.Event()
    reconfigure_vehicle.pair.side_effect = key_card_tapped.wait
    parent = MagicMock()
    parent.get_name.return_value = info.name
    parent.vehicles.createBluetooth.return_value = reconfigure_vehicle
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
        patch("homeassistant.components.teslemetry.PLATFORMS", [Platform.BUTTON]),
    ):
        result = await hass.config_entries.subentries.async_configure(flow_id, {})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "instructions"

        result = await hass.config_entries.subentries.async_configure(flow_id, {})
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["progress_action"] == "pair"
        # Waiting on the key card does not resolve the repair either.
        assert issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is not None

        key_card_tapped.set()
        await hass.async_block_till_done()
        result = await hass.config_entries.subentries.async_configure(flow_id)
        # The reconfigure schedules a reload, which unloads the router that raised the repair.
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    parent.vehicles.createBluetooth.assert_called_once_with(
        VEHICLE_VIN, device=info.device
    )
    reconfigure_vehicle.pair.assert_awaited_once()
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
    _, bluetooth_vehicles = await _raise_ble_key_issue(hass)
    bluetooth_vehicle = bluetooth_vehicles[VEHICLE_VIN]
    bluetooth_vehicle.handshakeVehicleSecurity.side_effect = NotOnWhitelistFault()
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
    assert bluetooth_vehicle.handshakeVehicleSecurity.await_count == handshakes
    assert not hass.config_entries.subentries.async_progress()
    assert issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is not None


@pytest.mark.usefixtures("enable_bluetooth")
async def test_ble_key_fix_flow_handshake_succeeds(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A key the vehicle accepts again over Bluetooth finishes the repair without re-pairing."""
    _, bluetooth_vehicles = await _raise_ble_key_issue(hass)
    bluetooth_vehicle = bluetooth_vehicles[VEHICLE_VIN]
    bluetooth_vehicle.handshakeVehicleSecurity.return_value = None
    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, BLE_KEY_ISSUE_ID)

    result = await _submit_ble_key_fix_flow(client, result["flow_id"], MagicMock())

    assert result["type"] == FlowResultType.CREATE_ENTRY
    bluetooth_vehicle.handshakeVehicleSecurity.assert_awaited_once_with()
    bluetooth_vehicle.disconnect.assert_not_awaited()
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
async def test_ble_key_fix_flow_key_still_rejected(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    key_error: TeslaFleetError,
) -> None:
    """Either key rejection from the Bluetooth handshake hands off to the reconfigure flow."""
    _, bluetooth_vehicles = await _raise_ble_key_issue(hass)
    bluetooth_vehicle = bluetooth_vehicles[VEHICLE_VIN]
    bluetooth_vehicle.handshakeVehicleSecurity.side_effect = key_error
    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, BLE_KEY_ISSUE_ID)

    result = await _submit_ble_key_fix_flow(client, result["flow_id"], MagicMock())

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure"
    assert result["next_flow"][0] == FlowType.CONFIG_SUBENTRIES_FLOW
    bluetooth_vehicle.handshakeVehicleSecurity.assert_awaited_once_with()
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
    disconnect_side_effect: BaseException | Callable[[], Awaitable[None]] | None,
) -> None:
    """A rejected key releases the repair's Bluetooth link before the reconfigure flow opens its own."""
    entry, bluetooth_vehicles = await _raise_ble_key_issue(hass)
    bluetooth_vehicle = bluetooth_vehicles[VEHICLE_VIN]
    bluetooth_vehicle.handshakeVehicleSecurity.side_effect = NotOnWhitelistFault()
    bluetooth_vehicle.disconnect.side_effect = disconnect_side_effect
    subentry = _vehicle_subentry(entry)
    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, BLE_KEY_ISSUE_ID)

    # One parent records both calls, so their order can be asserted.
    calls = MagicMock()
    calls.attach_mock(bluetooth_vehicle.disconnect, "disconnect")
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
    bluetooth_vehicle.disconnect.side_effect = None

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
    mock_products: MagicMock,
    mock_metadata: MagicMock,
) -> None:
    """Another vehicle accepting its key cannot clear this vehicle's repair."""
    products = deepcopy(PRODUCTS)
    other_product = deepcopy(products["response"][0])
    other_product["vin"] = OTHER_VIN
    other_product["display_name"] = "Other"
    # Listed first so the repair cannot find the right router by position.
    products["response"].insert(0, other_product)
    mock_products.return_value = products
    metadata = deepcopy(METADATA)
    metadata["vehicles"][OTHER_VIN] = metadata["vehicles"][VEHICLE_VIN]
    mock_metadata.return_value = metadata
    _, bluetooth_vehicles = await _raise_ble_key_issue(hass)
    bluetooth_vehicle = bluetooth_vehicles[VEHICLE_VIN]
    bluetooth_vehicle.handshakeVehicleSecurity.side_effect = NotOnWhitelistFault()
    other_bluetooth_vehicle = bluetooth_vehicles[OTHER_VIN]
    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, BLE_KEY_ISSUE_ID)

    result = await _submit_ble_key_fix_flow(client, result["flow_id"], MagicMock())

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure"
    bluetooth_vehicle.handshakeVehicleSecurity.assert_awaited_once_with()
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
    handshake_side_effect: BaseException | Callable[[], Awaitable[None]] | None,
    error: str,
    handshakes: int,
) -> None:
    """A handshake that cannot prove the key either way re-shows the form without re-pairing."""
    _, bluetooth_vehicles = await _raise_ble_key_issue(hass)
    bluetooth_vehicle = bluetooth_vehicles[VEHICLE_VIN]
    bluetooth_vehicle.handshakeVehicleSecurity.side_effect = handshake_side_effect
    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, BLE_KEY_ISSUE_ID)

    # Bound the hung handshake without waiting out the real timeout.
    with patch("homeassistant.components.teslemetry.repairs.BLE_HANDSHAKE_TIMEOUT", 0):
        result = await _submit_ble_key_fix_flow(client, result["flow_id"], ble_device)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": error}
    assert bluetooth_vehicle.handshakeVehicleSecurity.await_count == handshakes
    bluetooth_vehicle.disconnect.assert_not_awaited()
    assert not hass.config_entries.subentries.async_progress()
    assert issue_registry.async_get_issue(DOMAIN, BLE_KEY_ISSUE_ID) is not None


async def _unload_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Unload the entry."""
    assert await hass.config_entries.async_unload(entry.entry_id)


async def _remove_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Remove the entry."""
    await hass.config_entries.async_remove(entry.entry_id)


async def _remove_subentry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Remove the vehicle's Bluetooth subentry, which reloads the entry onto the cloud."""
    hass.config_entries.async_remove_subentry(
        entry, _vehicle_subentry(entry).subentry_id
    )
    await hass.async_block_till_done()


async def _reload_without_vehicle(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Reload the entry after the vehicle has left the account."""
    products = deepcopy(PRODUCTS)
    products["response"] = [
        product for product in products["response"] if product.get("vin") != VEHICLE_VIN
    ]
    with patch("tesla_fleet_api.teslemetry.Teslemetry.products", return_value=products):
        assert await hass.config_entries.async_reload(entry.entry_id)


@pytest.mark.usefixtures("enable_bluetooth")
@pytest.mark.parametrize(
    "lose_bluetooth_router",
    [
        pytest.param(_unload_entry, id="entry_unloaded"),
        pytest.param(_remove_entry, id="entry_removed"),
        pytest.param(_remove_subentry, id="subentry_removed"),
        pytest.param(_reload_without_vehicle, id="vehicle_left_account"),
    ],
)
async def test_ble_key_fix_flow_bluetooth_not_loaded(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    lose_bluetooth_router: Callable[[HomeAssistant, MockConfigEntry], Awaitable[None]],
) -> None:
    """A vehicle that loses its Bluetooth router while the fix flow is open aborts instead of guessing."""
    entry, bluetooth_vehicles = await _raise_ble_key_issue(hass)
    bluetooth_vehicle = bluetooth_vehicles[VEHICLE_VIN]
    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, BLE_KEY_ISSUE_ID)
    with patch("homeassistant.components.teslemetry.PLATFORMS", [Platform.BUTTON]):
        await lose_bluetooth_router(hass, entry)

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
