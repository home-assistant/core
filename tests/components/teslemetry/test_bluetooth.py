"""Test the Teslemetry Bluetooth routing and subentry pairing flow."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.exc import BleakError
import pytest
from tesla_fleet_api.exceptions import (
    BluetoothCommandFailed,
    BluetoothTimeout,
    BluetoothTransportError,
    BluetoothUnconfirmedCommand,
    NotOnWhitelistFault,
    TeslaFleetError,
    WhitelistOperationAttemptingToAddExistingKey,
)
from tesla_fleet_api.tesla import VehicleRouter
from tesla_fleet_api.tesla.bluetooth import TeslaBluetooth
from tesla_fleet_api.teslemetry import Vehicle

from homeassistant.components.teslemetry.const import (
    CONF_VIN,
    DOMAIN,
    SUBENTRY_TYPE_VEHICLE,
)
from homeassistant.components.teslemetry.helpers import async_get_ble_parent
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import mock_config_entry

from tests.common import MockConfigEntry

VIN = "LRW3F7EK4NC700000"
ADDRESS = "AA:BB:CC:DD:EE:FF"
CLOUD_RESULT = {"response": {"result": True, "reason": "cloud"}}
BLE_RESULT = {"response": {"result": True, "reason": "bluetooth"}}


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
    # Avoid replaying ambiguous commands or keeping the vehicle awake.
    mock_parent.return_value.vehicles.createBluetooth.assert_called_once_with(
        VIN,
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


@asynccontextmanager
async def _paired_entry(
    hass: HomeAssistant, ble_lookup: MagicMock
) -> AsyncIterator[tuple[VehicleRouter, AsyncMock, AsyncMock]]:
    """Set up a BLE-paired entry, yielding its router and both backends."""
    entry = _entry_with_ble()
    entry.add_to_hass(hass)
    bluetooth_vehicle = AsyncMock()
    bluetooth_vehicle.set_device = MagicMock()

    with (
        patch(
            "homeassistant.components.teslemetry.async_ble_device_from_address",
            ble_lookup,
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
        cloud = AsyncMock(return_value=CLOUD_RESULT)
        router.secondary.flash_lights = cloud
        yield router, bluetooth_vehicle, cloud


async def test_vehicle_bluetooth_out_of_range(hass: HomeAssistant) -> None:
    """A paired vehicle out of range still gets a router, and skips Bluetooth."""
    async with _paired_entry(hass, MagicMock(return_value=None)) as (
        router,
        bluetooth_vehicle,
        cloud,
    ):
        assert isinstance(router, VehicleRouter)

        assert await router.flash_lights() == CLOUD_RESULT

        cloud.assert_awaited_once()
        bluetooth_vehicle.flash_lights.assert_not_called()


async def test_vehicle_router_resumes_bluetooth_when_vehicle_returns(
    hass: HomeAssistant,
) -> None:
    """A vehicle away at setup routes locally again once it comes home."""
    ble_lookup = MagicMock(return_value=None)

    async with _paired_entry(hass, ble_lookup) as (router, bluetooth_vehicle, cloud):
        bluetooth_vehicle.flash_lights.return_value = BLE_RESULT

        assert await router.flash_lights() == CLOUD_RESULT
        bluetooth_vehicle.flash_lights.assert_not_called()

        ble_lookup.return_value = MagicMock()

        assert await router.flash_lights() == BLE_RESULT
        bluetooth_vehicle.flash_lights.assert_awaited_once()
        cloud.assert_awaited_once()


async def test_vehicle_router_falls_back_when_vehicle_leaves(
    hass: HomeAssistant,
) -> None:
    """A vehicle in range at setup routes to cloud once it drives away."""
    ble_lookup = MagicMock(return_value=MagicMock())

    async with _paired_entry(hass, ble_lookup) as (router, bluetooth_vehicle, cloud):
        bluetooth_vehicle.flash_lights.return_value = BLE_RESULT

        assert await router.flash_lights() == BLE_RESULT
        cloud.assert_not_called()

        ble_lookup.return_value = None

        assert await router.flash_lights() == CLOUD_RESULT
        cloud.assert_awaited_once()
        bluetooth_vehicle.flash_lights.assert_awaited_once()


async def test_vehicle_router_refreshes_device_handle(hass: HomeAssistant) -> None:
    """Each command refreshes the BLE handle from the cache before connecting."""
    first_device = MagicMock()
    second_device = MagicMock()
    ble_lookup = MagicMock(return_value=first_device)

    async with _paired_entry(hass, ble_lookup) as (router, bluetooth_vehicle, _cloud):
        await router.flash_lights()
        bluetooth_vehicle.set_device.assert_called_once_with(first_device)

        ble_lookup.return_value = second_device
        await router.flash_lights()

        bluetooth_vehicle.set_device.assert_called_with(second_device)


async def test_vehicle_router_fails_over_on_stale_cache_hit(
    hass: HomeAssistant,
) -> None:
    """A cache entry outliving the vehicle costs one failed attempt, not a failure."""
    async with _paired_entry(hass, MagicMock(return_value=MagicMock())) as (
        router,
        bluetooth_vehicle,
        cloud,
    ):
        bluetooth_vehicle.flash_lights.side_effect = BluetoothTransportError()

        assert await router.flash_lights() == CLOUD_RESULT

        bluetooth_vehicle.flash_lights.assert_awaited_once()
        cloud.assert_awaited_once()


async def test_vehicle_paired_but_never_seen(hass: HomeAssistant) -> None:
    """A paired vehicle never seen by Bluetooth is built without a device handle."""
    entry = _entry_with_ble()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.teslemetry.async_ble_device_from_address",
            MagicMock(return_value=None),
        ),
        patch(
            "homeassistant.components.teslemetry.helpers.TeslaBluetooth"
        ) as mock_parent,
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        mock_parent.return_value.get_private_key = AsyncMock()
        mock_parent.return_value.vehicles.createBluetooth.return_value = AsyncMock()
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert (
        "device"
        not in mock_parent.return_value.vehicles.createBluetooth.call_args.kwargs
    )


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


async def test_unload_never_connected_bluetooth(hass: HomeAssistant) -> None:
    """Unloading a paired vehicle that was never in range does not raise."""
    entry = _entry_with_ble()
    entry.add_to_hass(hass)
    bluetooth_vehicle = AsyncMock()

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
        mock_parent.return_value.vehicles.createBluetooth.return_value = (
            bluetooth_vehicle
        )
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

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
    """Concurrent first-time callers still create and load the key exactly once."""

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


def _entry_with_vehicle_subentry() -> MockConfigEntry:
    """Return a config entry with an added, not-yet-BLE-paired vehicle subentry."""
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
                data={CONF_VIN: VIN},
            )
        ],
    )


async def _setup_vehicle_subentry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up an entry that already has a vehicle subentry (no BLE address yet)."""
    entry = _entry_with_vehicle_subentry()
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
    """Each pairing failure surfaces its own error, not a blanket timeout."""
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


async def test_subentry_authorize_existing_key_finishes(hass: HomeAssistant) -> None:
    """Approving the key after a timeout, then retrying, completes the pairing."""
    entry = await _setup_vehicle_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)[0].subentry_id
    vehicle = _mock_vehicle(on_whitelist=False)
    releases = [asyncio.Event(), asyncio.Event()]
    attempts = iter(
        zip(
            releases,
            [BluetoothTimeout(), WhitelistOperationAttemptingToAddExistingKey()],
            strict=True,
        )
    )

    async def _pair() -> None:
        release, error = next(attempts)
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
        patch.object(hass.config_entries, "async_schedule_reload"),
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

        # the vehicle never confirms -> instructions re-shown, asking for approval
        releases[0].set()
        await hass.async_block_till_done()
        result = await hass.config_entries.subentries.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "timeout"}

        # the user approves the key and retries -> pair() runs again
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS

        # the vehicle reports the key already exists -> handshake confirms -> finish
        releases[1].set()
        await hass.async_block_till_done()
        result = await hass.config_entries.subentries.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.subentries[subentry_id].data[CONF_ADDRESS] == ADDRESS
    assert vehicle.pair.await_count == 2
    vehicle.disconnect.assert_awaited_once()


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


async def test_no_subentry_auto_created_at_setup(hass: HomeAssistant) -> None:
    """Setup never auto-creates a Bluetooth subentry for account vehicles."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    with patch("homeassistant.components.teslemetry.PLATFORMS", []):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert not entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)


async def test_user_subentry_persists_across_reload(hass: HomeAssistant) -> None:
    """A user-added vehicle subentry is never auto-removed on reload."""
    entry = await _setup_vehicle_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)[0].subentry_id

    with (
        patch(
            "tesla_fleet_api.teslemetry.Teslemetry.products",
            return_value={"response": []},
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
    """An awake in-range car only in scan responses is found via active scan."""
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


async def test_subentry_add_flow_creates_bound_subentry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """The add flow lists an account vehicle, pairs it, and binds its device."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # No Bluetooth subentry exists until the user adds one.
    assert not entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)
    existing_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, VIN), entry.entry_id
    )
    assert existing_device is not None
    # The device and its entities start on the parent entry, owned by no subentry.
    assert existing_device.config_subentry_id is None
    vehicle_entities = er.async_entries_for_device(
        entity_registry, existing_device.id, include_disabled_entities=True
    )
    assert vehicle_entities
    assert all(entity.config_subentry_id is None for entity in vehicle_entities)

    vehicle = _mock_vehicle(on_whitelist=True)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_VEHICLE),
        context={"source": "user"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # async_schedule_reload is deliberately left unpatched: the subentry is
    # committed only after the flow step returns, so the real reload the parent
    # entry's subentry-change listener schedules must run here with the BLE
    # address present. Keep the setup-time Bluetooth mocks active so that reload
    # neither writes the vehicle key file nor opens a real connection.
    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
            return_value=[_discovered_info()],
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.async_get_ble_parent",
            return_value=_mock_ble_parent(vehicle),
        ),
        patch(
            "homeassistant.components.teslemetry.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.teslemetry.helpers.TeslaBluetooth"
        ) as mock_parent,
    ):
        mock_parent.return_value.get_private_key = AsyncMock()
        mock_parent.return_value.vehicles.createBluetooth.return_value = MagicMock()

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_VIN: VIN}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "scan"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        # The subentry commits after the flow step returns; its change listener
        # then schedules the reload, which runs to completion here.
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY

    subentries = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)
    assert len(subentries) == 1
    subentry = subentries[0]
    assert subentry.unique_id == VIN
    assert subentry.data == {CONF_VIN: VIN, CONF_ADDRESS: ADDRESS}

    # The real reload picked up the stored address: the reloaded vehicle now
    # routes over Bluetooth instead of staying cloud-only.
    assert isinstance(entry.runtime_data.vehicles[0].api, VehicleRouter)

    # The pairing attaches to the vehicle's existing device, never a duplicate.
    bound_devices = [
        device
        for device in device_registry.devices.values()
        if (DOMAIN, VIN) in device.identifiers
    ]
    assert len(bound_devices) == 1
    bound_device = bound_devices[0]
    # The same device ID is kept, now owned by the created subentry.
    assert bound_device.id == existing_device.id
    assert bound_device.config_subentry_id == subentry.subentry_id

    # The vehicle entities keep their unique IDs and now belong to the subentry.
    bound_entities = er.async_entries_for_device(
        entity_registry, bound_device.id, include_disabled_entities=True
    )
    assert {entity.unique_id for entity in bound_entities} == {
        entity.unique_id for entity in vehicle_entities
    }
    assert all(
        entity.config_subentry_id == subentry.subentry_id for entity in bound_entities
    )


async def test_subentry_add_flow_no_available_vehicles(hass: HomeAssistant) -> None:
    """The add flow aborts when every account vehicle is already added."""
    entry = await _setup_vehicle_subentry(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_VEHICLE),
        context={"source": "user"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_vehicles"
