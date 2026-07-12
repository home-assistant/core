"""Test the Teslemetry Bluetooth routing and subentry pairing flow."""

import asyncio
from copy import deepcopy
from unittest.mock import ANY, AsyncMock, MagicMock, patch

from bleak.exc import BleakError
import pytest
from tesla_fleet_api.exceptions import (
    BluetoothCommandFailed,
    BluetoothTimeout,
    BluetoothTransportError,
    BluetoothUnconfirmedCommand,
    NotOnWhitelistFault,
    TeslaFleetError,
)
from tesla_fleet_api.tesla import VehicleRouter
from tesla_fleet_api.tesla.bluetooth import TeslaBluetooth
from tesla_fleet_api.teslemetry import Vehicle

from homeassistant.components.teslemetry import _ensure_subentry
from homeassistant.components.teslemetry.const import CONF_VIN, SUBENTRY_TYPE_VEHICLE
from homeassistant.components.teslemetry.helpers import async_get_ble_parent
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import mock_config_entry
from .const import METADATA

from tests.common import MockConfigEntry

VIN = "LRW3F7EK4NC700000"
ADDRESS = "AA:BB:CC:DD:EE:FF"


def _entry_with_ble() -> MockConfigEntry:
    """Return a config entry whose vehicle subentry is already BLE-paired."""
    entry = mock_config_entry()
    return MockConfigEntry(
        domain=entry.domain,
        version=entry.version,
        minor_version=entry.minor_version,
        unique_id=entry.unique_id,
        data=dict(entry.data),
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_VEHICLE,
                unique_id=VIN,
                title="Test",
                data={CONF_VIN: VIN, CONF_ADDRESS: ADDRESS},
            )
        ],
    )


async def test_vehicle_router_with_bluetooth(hass: HomeAssistant) -> None:
    """A BLE-paired vehicle wraps its cloud API in a VehicleRouter."""
    entry = _entry_with_ble()
    entry.add_to_hass(hass)

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
        mock_parent.return_value.vehicles.createBluetooth.return_value = MagicMock()
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    vehicle = entry.runtime_data.vehicles[0]
    assert isinstance(vehicle.api, VehicleRouter)
    # confirmation="verify" reads state back on an ack+broadcast timeout to
    # confirm or prove-non-application; raise_unconfirmed=False keeps a
    # still-ambiguous outcome a best-effort success so the router never re-sends
    # a non-idempotent command to cloud; keepalive is off for command-only use.
    mock_parent.return_value.vehicles.createBluetooth.assert_called_once_with(
        VIN,
        device=ANY,
        confirmation="verify",
        raise_unconfirmed=False,
        keepalive_interval=None,
    )


async def test_vehicle_cloud_without_bluetooth(hass: HomeAssistant) -> None:
    """A vehicle without a paired address keeps the plain cloud API."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    with patch("homeassistant.components.teslemetry.PLATFORMS", []):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    vehicle = entry.runtime_data.vehicles[0]
    assert isinstance(vehicle.api, Vehicle)
    assert not isinstance(vehicle.api, VehicleRouter)


async def test_vehicle_bluetooth_out_of_range(hass: HomeAssistant) -> None:
    """A paired vehicle out of BLE range falls back to cloud only for this run."""
    entry = _entry_with_ble()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.teslemetry.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.teslemetry.helpers.TeslaBluetooth"
        ) as mock_parent,
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        mock_parent.return_value.get_private_key = AsyncMock()
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    vehicle = entry.runtime_data.vehicles[0]
    assert not isinstance(vehicle.api, VehicleRouter)


async def test_vehicle_router_after_cold_cache_active_scan(hass: HomeAssistant) -> None:
    """A paired vehicle missing from a cold discovery cache is found via one scan.

    async_ble_device_from_address() only reads the passive discovery cache;
    on a cold Home Assistant start the first advertisement may not have
    arrived yet even though the car is in range. A bounded active scan and
    retry must still route it locally instead of permanently falling back to
    cloud for the entry's whole lifetime.
    """
    entry = _entry_with_ble()
    entry.add_to_hass(hass)
    mock_ble_device = MagicMock(return_value=None)

    async def _active_scan(hass: HomeAssistant) -> None:
        mock_ble_device.return_value = MagicMock()

    with (
        patch(
            "homeassistant.components.teslemetry.async_ble_device_from_address",
            mock_ble_device,
        ),
        patch(
            "homeassistant.components.teslemetry.async_request_active_scan",
            AsyncMock(side_effect=_active_scan),
        ) as mock_active_scan,
        patch(
            "homeassistant.components.teslemetry.helpers.TeslaBluetooth"
        ) as mock_parent,
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        mock_parent.return_value.get_private_key = AsyncMock()
        mock_parent.return_value.vehicles.createBluetooth.return_value = MagicMock()
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    vehicle = entry.runtime_data.vehicles[0]
    mock_active_scan.assert_awaited_once()
    assert isinstance(vehicle.api, VehicleRouter)


@pytest.mark.parametrize(
    "disconnect_error",
    [None, BleakError("boom")],
    ids=["clean", "error_swallowed"],
)
async def test_unload_disconnects_bluetooth(
    hass: HomeAssistant, disconnect_error: Exception | None
) -> None:
    """Unloading a routed entry disconnects its Bluetooth backend, errors and all."""
    entry = _entry_with_ble()
    entry.add_to_hass(hass)
    bluetooth_vehicle = AsyncMock()
    bluetooth_vehicle.disconnect = AsyncMock(side_effect=disconnect_error)

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
        assert isinstance(entry.runtime_data.vehicles[0].api, VehicleRouter)

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    bluetooth_vehicle.disconnect.assert_awaited_once()


async def test_ble_parent_shared_and_cached(hass: HomeAssistant) -> None:
    """The BLE parent (holding the private key) is created once and reused."""
    with patch(
        "homeassistant.components.teslemetry.helpers.TeslaBluetooth"
    ) as mock_parent:
        mock_parent.return_value.get_private_key = AsyncMock()
        first = await async_get_ble_parent(hass)
        second = await async_get_ble_parent(hass)

    assert first is second
    mock_parent.assert_called_once()
    mock_parent.return_value.get_private_key.assert_awaited_once()


async def test_ble_parent_concurrent_first_init(hass: HomeAssistant) -> None:
    """Concurrent first-time callers still create and load the key exactly once.

    Without the init lock, callers racing before the parent is cached would
    each construct their own TeslaBluetooth and generate/overwrite the key.
    """

    async def _get_private_key(path: str) -> None:
        await asyncio.sleep(0)

    with patch(
        "homeassistant.components.teslemetry.helpers.TeslaBluetooth"
    ) as mock_parent:
        mock_parent.return_value.get_private_key = AsyncMock(
            side_effect=_get_private_key
        )
        parents = await asyncio.gather(*(async_get_ble_parent(hass) for _ in range(5)))

    assert all(parent is parents[0] for parent in parents)
    mock_parent.assert_called_once()
    mock_parent.return_value.get_private_key.assert_awaited_once()


async def test_ensure_subentry_preserves_paired_address(hass: HomeAssistant) -> None:
    """Re-ensuring a subentry keeps the paired address and applies a new title."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    first = _ensure_subentry(
        hass, entry, SUBENTRY_TYPE_VEHICLE, VIN, "Old name", {CONF_VIN: VIN}
    )
    hass.config_entries.async_update_subentry(
        entry,
        entry.subentries[first],
        data={CONF_VIN: VIN, CONF_ADDRESS: ADDRESS},
    )

    second = _ensure_subentry(
        hass, entry, SUBENTRY_TYPE_VEHICLE, VIN, "New name", {CONF_VIN: VIN}
    )

    assert first == second
    assert entry.subentries[second].title == "New name"
    # The paired address added out of band must survive the re-ensure merge.
    assert entry.subentries[second].data[CONF_ADDRESS] == ADDRESS


async def test_router_does_not_fail_over_on_unconfirmed() -> None:
    """An unconfirmed BLE command is never replayed on the cloud backend."""
    bluetooth = AsyncMock()
    bluetooth.actuate_trunk = AsyncMock(side_effect=BluetoothUnconfirmedCommand())
    cloud = AsyncMock()
    cloud.actuate_trunk = AsyncMock(return_value={"response": {"result": True}})
    router = VehicleRouter(bluetooth, cloud)

    with pytest.raises(BluetoothUnconfirmedCommand):
        await router.actuate_trunk()

    cloud.actuate_trunk.assert_not_called()


async def test_router_fails_over_on_command_failed() -> None:
    """A command proven not to have applied over BLE fails over to the cloud."""
    bluetooth = AsyncMock()
    bluetooth.actuate_trunk = AsyncMock(side_effect=BluetoothCommandFailed())
    cloud = AsyncMock()
    cloud.actuate_trunk = AsyncMock(return_value={"response": {"result": True}})
    router = VehicleRouter(bluetooth, cloud)

    result = await router.actuate_trunk()

    assert result == {"response": {"result": True}}
    bluetooth.actuate_trunk.assert_awaited_once()
    cloud.actuate_trunk.assert_awaited_once()


def _discovered_info() -> MagicMock:
    """Return a fake discovered service info matching the test VIN."""
    info = MagicMock()
    info.name = TeslaBluetooth().get_name(VIN)
    info.address = ADDRESS
    info.device = MagicMock()
    return info


def _mock_vehicle(*, on_whitelist: bool = True) -> AsyncMock:
    """Return a mock VehicleBluetooth for the pairing flow."""
    vehicle = AsyncMock()
    if on_whitelist:
        vehicle.handshakeVehicleSecurity = AsyncMock()
    else:
        vehicle.handshakeVehicleSecurity = AsyncMock(
            side_effect=[NotOnWhitelistFault(), None]
        )
    return vehicle


def _mock_ble_parent(vehicle: AsyncMock | None = None) -> MagicMock:
    """Return a mock shared TeslaBluetooth parent for the pairing flow."""
    parent = MagicMock()
    parent.get_name.return_value = TeslaBluetooth().get_name(VIN)
    if vehicle is not None:
        parent.vehicles.createBluetooth.return_value = vehicle
    return parent


async def _setup_vehicle_subentry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up an entry and return it with a vehicle subentry (no BLE yet)."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)
    with patch("homeassistant.components.teslemetry.PLATFORMS", []):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_subentry_pairing_already_whitelisted(hass: HomeAssistant) -> None:
    """Pairing succeeds immediately when the virtual key is already whitelisted."""
    entry = await _setup_vehicle_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)[0].subentry_id
    vehicle = _mock_vehicle(on_whitelist=True)
    address_stored_at_reload = False

    def _capture_reload(entry_id: str) -> None:
        nonlocal address_stored_at_reload
        address_stored_at_reload = (
            entry.subentries[subentry_id].data.get(CONF_ADDRESS) == ADDRESS
        )

    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
            return_value=[_discovered_info()],
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.async_get_ble_parent",
            return_value=_mock_ble_parent(vehicle),
        ),
        patch.object(
            hass.config_entries, "async_schedule_reload", side_effect=_capture_reload
        ) as mock_reload,
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "scan"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.subentries[subentry_id].data[CONF_ADDRESS] == ADDRESS
    mock_reload.assert_called_once_with(entry.entry_id)
    # The address must already be persisted by the time the reload is scheduled.
    assert address_stored_at_reload
    vehicle.connect.assert_awaited_once()
    vehicle.disconnect.assert_awaited_once()


async def test_subentry_pairing_requires_key_approval(hass: HomeAssistant) -> None:
    """Pairing walks through instructions and key install when not whitelisted."""
    entry = await _setup_vehicle_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)[0].subentry_id
    vehicle = _mock_vehicle(on_whitelist=False)
    release = asyncio.Event()

    async def _pair() -> None:
        await release.wait()

    vehicle.pair = AsyncMock(side_effect=_pair)

    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
            return_value=[_discovered_info()],
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.async_get_ble_parent",
            return_value=_mock_ble_parent(vehicle),
        ),
        patch.object(hass.config_entries, "async_schedule_reload"),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        # scan -> connect -> handshake raises NotOnWhitelistFault -> instructions
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "instructions"

        # confirm instructions -> authorize runs pair() as a progress task
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["progress_action"] == "pair"

        # pair() completes -> progress done -> handshake ok -> finish
        release.set()
        await hass.async_block_till_done()
        result = await hass.config_entries.subentries.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.subentries[subentry_id].data[CONF_ADDRESS] == ADDRESS
    vehicle.pair.assert_awaited_once()


async def test_subentry_scan_connect_fails(hass: HomeAssistant) -> None:
    """The scan step re-shows the form with an error when BLE connect fails."""
    entry = await _setup_vehicle_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)[0].subentry_id
    vehicle = _mock_vehicle()
    vehicle.connect = AsyncMock(side_effect=BleakError("nope"))

    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
            return_value=[_discovered_info()],
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.async_get_ble_parent",
            return_value=_mock_ble_parent(vehicle),
        ),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "scan"
    assert result["errors"] == {"base": "cannot_connect"}
    assert CONF_ADDRESS not in entry.subentries[subentry_id].data
    vehicle.disconnect.assert_awaited_once()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (BluetoothTimeout, "timeout"),
        (BluetoothTransportError, "cannot_connect"),
        (TeslaFleetError, "pair_failed"),
    ],
    ids=["timeout", "transport", "rejected"],
)
async def test_subentry_authorize_failure(
    hass: HomeAssistant, error: type[TeslaFleetError], expected: str
) -> None:
    """Each pairing failure surfaces its own error, not a blanket timeout.

    A confirmation timeout, a transport failure, and an explicit key rejection
    (e.g. whitelist full or valet mode) are reported distinctly.
    """
    entry = await _setup_vehicle_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)[0].subentry_id
    vehicle = _mock_vehicle(on_whitelist=False)
    release = asyncio.Event()

    async def _pair() -> None:
        await release.wait()
        raise error

    vehicle.pair = AsyncMock(side_effect=_pair)

    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
            return_value=[_discovered_info()],
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.async_get_ble_parent",
            return_value=_mock_ble_parent(vehicle),
        ),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["step_id"] == "instructions"

        # confirm instructions -> authorize runs pair() as a progress task
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS

        # pair() fails -> progress done -> instructions re-shown with the error
        release.set()
        await hass.async_block_till_done()
        result = await hass.config_entries.subentries.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "instructions"
    assert result["errors"] == {"base": expected}
    assert CONF_ADDRESS not in entry.subentries[subentry_id].data
    # pair() is a single bounded op; it is never re-sent.
    vehicle.pair.assert_awaited_once()


async def test_subentry_handshake_error_aborts(hass: HomeAssistant) -> None:
    """A handshake failure aborts with cannot_connect; a disconnect error is swallowed."""
    entry = await _setup_vehicle_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)[0].subentry_id
    vehicle = _mock_vehicle()
    vehicle.handshakeVehicleSecurity = AsyncMock(side_effect=TeslaFleetError())
    vehicle.disconnect = AsyncMock(side_effect=BleakError("boom"))

    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
            return_value=[_discovered_info()],
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.async_get_ble_parent",
            return_value=_mock_ble_parent(vehicle),
        ),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    assert CONF_ADDRESS not in entry.subentries[subentry_id].data
    vehicle.disconnect.assert_awaited_once()


async def test_subentry_pairing_abandoned(hass: HomeAssistant) -> None:
    """Abandoning the flow mid-pairing cancels the pair task and disconnects."""
    entry = await _setup_vehicle_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)[0].subentry_id
    vehicle = _mock_vehicle(on_whitelist=False)
    cancelled = asyncio.Event()

    async def _pair() -> None:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    vehicle.pair = AsyncMock(side_effect=_pair)

    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
            return_value=[_discovered_info()],
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.async_get_ble_parent",
            return_value=_mock_ble_parent(vehicle),
        ),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        # confirm instructions -> authorize runs pair() as a progress task
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS

        # abandon the flow while pairing is still running
        hass.config_entries.subentries.async_abort(result["flow_id"])
        await hass.async_block_till_done()

    assert cancelled.is_set()
    vehicle.disconnect.assert_awaited_once()
    assert CONF_ADDRESS not in entry.subentries[subentry_id].data


async def test_subentry_removal_reloads(hass: HomeAssistant) -> None:
    """Removing a vehicle subentry reloads once; later updates do not re-schedule."""
    entry = await _setup_vehicle_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)[0].subentry_id

    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        assert hass.config_entries.async_remove_subentry(entry, subentry_id)
        await hass.async_block_till_done()

        # A later entry update before the reload runs must not re-schedule it.
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "marker": True}
        )
        await hass.async_block_till_done()

    mock_reload.assert_called_once_with(entry.entry_id)


async def test_stale_vehicle_subentry_removed_on_reload(hass: HomeAssistant) -> None:
    """A vehicle subentry no longer backed by the account is removed on reload.

    This cleanup deletes the subentry's persisted pairing data (the BLE
    address), not just a device-registry entry.
    """
    entry = await _setup_vehicle_subentry(hass)
    assert entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)

    with (
        patch(
            "tesla_fleet_api.teslemetry.Teslemetry.products",
            return_value={"response": []},
        ),
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert not entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)


async def test_vehicle_subentry_retained_without_access(hass: HomeAssistant) -> None:
    """A vehicle subentry is kept when the vehicle is only temporarily inaccessible.

    The stale-subentry cleanup must key off vehicles still in the account's
    product list, not the access-filtered active vehicle list; otherwise a
    transient subscription/scope change would delete the persisted BLE
    pairing address and force the user to re-pair once access returns.
    """
    entry = await _setup_vehicle_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)[0].subentry_id

    no_access_metadata = deepcopy(METADATA)
    no_access_metadata["vehicles"][VIN]["access"] = False

    with (
        patch(
            "tesla_fleet_api.teslemetry.Teslemetry.metadata",
            return_value=no_access_metadata,
        ),
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    subentries = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)
    assert len(subentries) == 1
    assert subentries[0].subentry_id == subentry_id


async def test_subentry_scan_device_not_found(hass: HomeAssistant) -> None:
    """The scan step re-shows the form with an error when no device is found."""
    entry = await _setup_vehicle_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)[0].subentry_id

    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
            return_value=[],
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.async_get_ble_parent",
            return_value=_mock_ble_parent(),
        ),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "scan"
    assert result["errors"] == {"base": "device_not_found"}
    assert CONF_ADDRESS not in entry.subentries[subentry_id].data


async def test_subentry_scan_finds_device_after_active_scan(
    hass: HomeAssistant,
) -> None:
    """An awake in-range car only in scan responses is found via active scan.

    async_discovered_service_info() is a cache read; a car whose name is
    still missing from that cache (e.g. an AUTO-mode scanner has not swept
    recently) must be found once an active scan is requested, not reported
    as not found.
    """
    entry = await _setup_vehicle_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)[0].subentry_id
    vehicle = _mock_vehicle()
    mock_discovered = MagicMock(return_value=[])

    async def _active_scan(hass: HomeAssistant) -> None:
        mock_discovered.return_value = [_discovered_info()]

    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
            mock_discovered,
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.async_request_active_scan",
            AsyncMock(side_effect=_active_scan),
        ) as mock_active_scan,
        patch(
            "homeassistant.components.teslemetry.config_flow.async_get_ble_parent",
            return_value=_mock_ble_parent(vehicle),
        ),
        patch.object(hass.config_entries, "async_schedule_reload"),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        await hass.async_block_till_done()

    mock_active_scan.assert_awaited_once()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.subentries[subentry_id].data[CONF_ADDRESS] == ADDRESS
    vehicle.connect.assert_awaited_once()


async def test_subentry_user_step_rejected(hass: HomeAssistant) -> None:
    """Manually adding a vehicle subentry is rejected."""
    entry = await _setup_vehicle_subentry(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_VEHICLE),
        context={"source": "user"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"
