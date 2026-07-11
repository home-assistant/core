"""Test the Teslemetry Bluetooth routing and subentry pairing flow."""

from unittest.mock import ANY, AsyncMock, MagicMock, patch

from bleak.exc import BleakError
from tesla_fleet_api.exceptions import NotOnWhitelistFault
from tesla_fleet_api.tesla import VehicleRouter
from tesla_fleet_api.tesla.bluetooth import TeslaBluetooth
from tesla_fleet_api.teslemetry import Vehicle

from homeassistant.components.teslemetry.const import CONF_VIN, SUBENTRY_TYPE_VEHICLE
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import mock_config_entry

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
        patch("homeassistant.components.teslemetry.TeslaBluetooth") as mock_parent,
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        mock_parent.return_value.get_private_key = AsyncMock()
        mock_parent.return_value.vehicles.createBluetooth.return_value = MagicMock()
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    vehicle = entry.runtime_data.vehicles[0]
    assert isinstance(vehicle.api, VehicleRouter)
    # Mutating BLE commands must be verified by state so the router's
    # BLE->cloud failover cannot double-execute a non-idempotent command.
    mock_parent.return_value.vehicles.createBluetooth.assert_called_once_with(
        VIN, device=ANY, verify_commands=True, keepalive_interval=20
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
        patch("homeassistant.components.teslemetry.TeslaBluetooth") as mock_parent,
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        mock_parent.return_value.get_private_key = AsyncMock()
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    vehicle = entry.runtime_data.vehicles[0]
    assert not isinstance(vehicle.api, VehicleRouter)


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

    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
            return_value=[_discovered_info()],
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.TeslaBluetooth"
        ) as mock_parent,
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
    ):
        mock_parent.return_value.get_name.return_value = TeslaBluetooth().get_name(VIN)
        mock_parent.return_value.get_private_key = AsyncMock()
        mock_parent.return_value.vehicles.createBluetooth.return_value = vehicle

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
    vehicle.connect.assert_awaited_once()
    vehicle.disconnect.assert_awaited_once()


async def test_subentry_pairing_requires_key_approval(hass: HomeAssistant) -> None:
    """Pairing walks through instructions and key install when not whitelisted."""
    entry = await _setup_vehicle_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)[0].subentry_id
    vehicle = _mock_vehicle(on_whitelist=False)

    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
            return_value=[_discovered_info()],
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.TeslaBluetooth"
        ) as mock_parent,
        patch.object(hass.config_entries, "async_schedule_reload"),
    ):
        mock_parent.return_value.get_name.return_value = TeslaBluetooth().get_name(VIN)
        mock_parent.return_value.get_private_key = AsyncMock()
        mock_parent.return_value.vehicles.createBluetooth.return_value = vehicle

        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        # scan -> connect -> handshake raises NotOnWhitelistFault -> instructions
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "instructions"

        # confirm instructions -> authorize -> pair() -> handshake ok -> finish
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
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
            "homeassistant.components.teslemetry.config_flow.TeslaBluetooth"
        ) as mock_parent,
    ):
        mock_parent.return_value.get_name.return_value = TeslaBluetooth().get_name(VIN)
        mock_parent.return_value.get_private_key = AsyncMock()
        mock_parent.return_value.vehicles.createBluetooth.return_value = vehicle

        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "scan"
    assert result["errors"] == {"base": "cannot_connect"}
    assert CONF_ADDRESS not in entry.subentries[subentry_id].data


async def test_subentry_authorize_timeout(hass: HomeAssistant) -> None:
    """The instructions step re-shows with a timeout error if pairing never succeeds."""
    entry = await _setup_vehicle_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)[0].subentry_id
    vehicle = _mock_vehicle(on_whitelist=False)
    vehicle.pair = AsyncMock(side_effect=BleakError("still not approved"))

    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
            return_value=[_discovered_info()],
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.TeslaBluetooth"
        ) as mock_parent,
    ):
        mock_parent.return_value.get_name.return_value = TeslaBluetooth().get_name(VIN)
        mock_parent.return_value.get_private_key = AsyncMock()
        mock_parent.return_value.vehicles.createBluetooth.return_value = vehicle

        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["step_id"] == "instructions"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "instructions"
    assert result["errors"] == {"base": "timeout"}
    assert CONF_ADDRESS not in entry.subentries[subentry_id].data


async def test_subentry_scan_device_not_found(hass: HomeAssistant) -> None:
    """The scan step re-shows the form with an error when no device is found."""
    entry = await _setup_vehicle_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)[0].subentry_id

    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
            return_value=[],
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


async def test_subentry_user_step_rejected(hass: HomeAssistant) -> None:
    """Manually adding a vehicle subentry is rejected."""
    entry = await _setup_vehicle_subentry(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_VEHICLE),
        context={"source": "user"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"
