"""Test the coordinator."""

from home_assistant_bluetooth import BluetoothServiceInfoBleak

from homeassistant.components.bluetooth.models import BluetoothChange
from homeassistant.components.private_ble_device.coordinator import (
    async_get_coordinator,
)
from homeassistant.core import HomeAssistant

from tests.components.private_ble_device import (
    MAC_RPA_INVALID,
    MAC_RPA_VALID_1,
    MAC_RPA_VALID_2,
    MAC_STATIC,
    async_inject_broadcast,
    async_move_time_forwards,
)


async def test_get_coordinator(hass: HomeAssistant, enable_bluetooth: None):
    """Test that the coordinator is a singleton."""
    coord1 = async_get_coordinator(hass)
    coord2 = async_get_coordinator(hass)
    assert coord1 == coord2


async def test_track_unavailable_in_isolation(
    hass: HomeAssistant, enable_bluetooth: None
):
    """Test async_track_unavailable in isolation from async_track_service_info."""
    coordinator = async_get_coordinator(hass)

    unavailable = False

    def callback(service_info: BluetoothServiceInfoBleak) -> None:
        nonlocal unavailable
        unavailable = True

    cancel_fn = coordinator.async_track_unavailable(callback, b"\x00" * 16)

    await async_inject_broadcast(hass, MAC_RPA_VALID_1)
    await async_move_time_forwards(hass, 910)
    assert unavailable is True

    cancel_fn()


async def test_track_unavailable_in_isolation_2(
    hass: HomeAssistant, enable_bluetooth: None
):
    """Test async_track_unavailable not impacted by async_track_service_info."""
    coordinator = async_get_coordinator(hass)

    unavailable = False

    def callback(service_info: BluetoothServiceInfoBleak) -> None:
        nonlocal unavailable
        unavailable = True

    cancel_fn = coordinator.async_track_unavailable(callback, b"\x00" * 16)

    si_cancel_fn = coordinator.async_track_service_info(
        lambda *args: None, b"\x00" * 16
    )
    si_cancel_fn()

    await async_inject_broadcast(hass, MAC_RPA_VALID_1)
    await async_move_time_forwards(hass, 910)
    assert unavailable is True

    cancel_fn()


async def test_track_unavailable_cancellation(
    hass: HomeAssistant, enable_bluetooth: None
):
    """Test cancelling a async_track_unavailable works."""
    coordinator = async_get_coordinator(hass)

    unavailable = False

    def callback(service_info: BluetoothServiceInfoBleak) -> None:
        nonlocal unavailable
        unavailable = True

    cancel_fn = coordinator.async_track_unavailable(callback, b"\x00" * 16)
    cancel_fn()

    await async_inject_broadcast(hass, MAC_RPA_VALID_1)
    await async_move_time_forwards(hass, 910)
    assert unavailable is False


async def test_async_track_service_info_in_isolation(
    hass: HomeAssistant, enable_bluetooth: None
):
    """Test async_track_service_info in isolation from async_track_unavailable."""
    coordinator = async_get_coordinator(hass)

    callback_count = 0

    def callback(
        service_info: BluetoothServiceInfoBleak, change: BluetoothChange
    ) -> None:
        nonlocal callback_count
        callback_count += 1

    cancel_fn = coordinator.async_track_service_info(callback, b"\x00" * 16)

    await async_inject_broadcast(hass, MAC_RPA_VALID_1, b"1")
    assert callback_count == 1

    await async_inject_broadcast(hass, MAC_RPA_VALID_1, b"2")
    assert callback_count == 2

    await async_inject_broadcast(hass, MAC_RPA_VALID_2, b"1")
    assert callback_count == 3

    # Make sure unrelated non-random address doesn't trigger a callback
    await async_inject_broadcast(hass, MAC_STATIC, b"1")
    assert callback_count == 3

    # Make sure unrelated RPA doesn't trigger a callback
    await async_inject_broadcast(hass, MAC_RPA_INVALID, b"1")
    assert callback_count == 3

    # Make sure that the other API's don't interfere with this callback
    unavail_cancel_fn = coordinator.async_track_unavailable(
        lambda *args: None, b"\x00" * 16
    )
    unavail_cancel_fn()

    await async_inject_broadcast(hass, MAC_RPA_VALID_2, b"2")
    assert callback_count == 4

    cancel_fn()


async def test_async_track_service_info_cancellation(
    hass: HomeAssistant, enable_bluetooth: None
):
    """Test async_track_service_info can be cancelled."""
    coordinator = async_get_coordinator(hass)

    callback_count = 0

    def callback(
        service_info: BluetoothServiceInfoBleak, change: BluetoothChange
    ) -> None:
        nonlocal callback_count
        callback_count += 1

    cancel_fn = coordinator.async_track_service_info(callback, b"\x00" * 16)
    cancel_fn()

    await async_inject_broadcast(hass, MAC_RPA_VALID_1, b"1")
    assert callback_count == 0
