"""Test the BLE Battery Management System update coordinator."""

from collections.abc import Awaitable, Callable
import contextlib
from typing import Final

from aiobmsble import BMSSample
from habluetooth import BluetoothServiceInfoBleak
import pytest

from homeassistant.components.bms_ble.const import (
    ATTR_CURRENT,
    ATTR_CYCLE_CAP,
    ATTR_CYCLE_CHRG,
    ATTR_CYCLES,
    ATTR_POWER,
    ATTR_PROBLEM,
)
from homeassistant.components.bms_ble.coordinator import BTBmsCoordinator
from homeassistant.const import ATTR_BATTERY_CHARGING, ATTR_VOLTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import MockBMS, mock_config

from tests.components.bluetooth import inject_bluetooth_service_info_bleak


@pytest.mark.usefixtures("enable_bluetooth", "patch_default_bleak_client")
async def test_update(
    monkeypatch: pytest.MonkeyPatch,
    bool_fixture: bool,
    bt_discovery: BluetoothServiceInfoBleak,
    hass: HomeAssistant,
) -> None:
    """Test setting up creates the sensors."""

    def mock_last_service_info(hass: HomeAssistant, address, connectable) -> None:
        assert (
            isinstance(hass, HomeAssistant)
            and connectable is True
            and len(address) == 17
        ), "Call to get last advertisement is invalid."

    if (advertisement_avail := bool_fixture) is False:
        monkeypatch.setattr(
            "homeassistant.components.bms_ble.coordinator.async_last_service_info",
            mock_last_service_info,
        )

    coordinator = BTBmsCoordinator(
        hass, bt_discovery.device, MockBMS(), mock_config(bms="update")
    )

    inject_bluetooth_service_info_bleak(hass, bt_discovery)

    await coordinator.async_refresh()
    result: BMSSample = coordinator.data
    assert coordinator.last_update_success

    assert result == {
        ATTR_VOLTAGE: 13,
        ATTR_CURRENT: 1.7,
        ATTR_CYCLE_CAP: 247,
        ATTR_CYCLE_CHRG: 19,
        ATTR_CYCLES: 23,
        ATTR_POWER: 22.1,
        ATTR_PROBLEM: False,
        ATTR_BATTERY_CHARGING: True,
    }
    assert coordinator.rssi == (-61 if advertisement_avail else None)
    assert coordinator.link_quality == 50

    # second update (modify rssi, and check link quality again)
    bt_discovery.rssi = -85
    inject_bluetooth_service_info_bleak(hass, bt_discovery)
    await coordinator.async_refresh()
    result = coordinator.data

    assert coordinator.rssi == (-85 if advertisement_avail else None)
    assert coordinator.link_quality == 66

    await coordinator.async_shutdown()


@pytest.mark.usefixtures("enable_bluetooth", "patch_default_bleak_client")
async def test_nodata(
    bt_discovery: BluetoothServiceInfoBleak, hass: HomeAssistant
) -> None:
    """Test if coordinator raises exception in case no data, e.g. invalid CRC, is returned."""

    coordinator = BTBmsCoordinator(
        hass, bt_discovery.device, MockBMS(ret_value={}), mock_config(bms="nodata")
    )

    inject_bluetooth_service_info_bleak(hass, bt_discovery)

    await coordinator.async_refresh()
    result: BMSSample = coordinator.data
    assert not coordinator.last_update_success

    await coordinator.async_shutdown()

    assert result is None
    assert coordinator.rssi == -61
    assert coordinator.link_quality == 0


@pytest.mark.usefixtures("enable_bluetooth", "patch_default_bleak_client")
async def test_update_exception(
    bt_discovery: BluetoothServiceInfoBleak,
    mock_coordinator_exception: Exception,
    hass: HomeAssistant,
) -> None:
    """Test if coordinator raises appropriate exception from BMS."""

    coordinator = BTBmsCoordinator(
        hass,
        bt_discovery.device,
        MockBMS(mock_coordinator_exception),
        mock_config(bms="update_exception"),
    )

    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert isinstance(
        coordinator.last_exception,
        (
            TimeoutError
            if isinstance(mock_coordinator_exception, type)
            and issubclass(mock_coordinator_exception, TimeoutError)
            else UpdateFailed
        ),
    )


@pytest.mark.usefixtures("enable_bluetooth", "patch_default_bleak_client")
async def test_stale_recovery(
    monkeypatch: pytest.MonkeyPatch,
    bt_discovery: BluetoothServiceInfoBleak,
    hass: HomeAssistant,
) -> None:
    """Test if coordinator raises appropriate exception from BMS."""
    flags: dict[str, bool] = {"disconnect_called": False}
    bms_data: Final[MockBMS] = MockBMS()
    bms_nodata: Final[MockBMS] = MockBMS(ret_value={})
    bms_disconnect: Final[Callable[[MockBMS, bool], Awaitable[None]]] = (
        MockBMS.disconnect
    )

    async def _mock_disconnect(self, reset: bool = False) -> bool:
        """Mock disconnect method."""
        flags["reset"] = reset
        flags["disconnect_called"] = True
        await bms_disconnect(self, reset)
        return True

    monkeypatch.setattr(MockBMS, "disconnect", _mock_disconnect)

    coordinator = BTBmsCoordinator(
        hass,
        bt_discovery.device,
        bms_nodata,
        mock_config(bms="stale_recovery"),
    )

    # run 8 times failed update from beginning (1 failed is init value!)
    for _ in range(8):
        with contextlib.suppress(UpdateFailed):
            await coordinator.async_refresh()
        assert not coordinator.last_update_success
    assert coordinator.link_quality == 0
    assert not flags["disconnect_called"]  # should trigger tenth time, so not now

    # update once with valid data
    # (this will set the link quality to 10%, and reset the stale flag)
    monkeypatch.setattr(coordinator, "_device", bms_data)
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.link_quality == 10
    assert not flags["disconnect_called"]

    # run 10 times failed updates
    monkeypatch.setattr(coordinator, "_device", bms_nodata)
    for _ in range(10):
        with contextlib.suppress(UpdateFailed):
            await coordinator.async_refresh()
        assert not coordinator.last_update_success
        assert not flags["disconnect_called"]
    assert coordinator.link_quality == 5

    # since 10 consecutive updates failed and link quality is below 10%, reconnect shall trigger
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert coordinator.link_quality == 4
    assert flags["disconnect_called"]
    assert flags["reset"] is True, "Reset flag should be set on stale recovery"
