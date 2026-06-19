"""Tests for the Matter integration BLE proxy adapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from bleak.backends.device import BLEDevice
from bluetooth_data_tools import monotonic_time_coarse
from matter_ble_proxy import AdvertisementData
import pytest

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.matter.ble_proxy import (
    HaBluetoothDeviceResolver,
    HaBluetoothScanSource,
    _to_advertisement_data,
    create_matter_ble_proxy,
)
from homeassistant.core import HomeAssistant


def _make_service_info(time: float | None = None) -> BluetoothServiceInfoBleak:
    """Return a real BluetoothServiceInfoBleak with realistic field values."""
    address = "AA:BB:CC:DD:EE:FF"
    name = "TestDevice"
    return BluetoothServiceInfoBleak(
        name=name,
        address=address,
        rssi=-55,
        manufacturer_data={0x004C: b"\x01\x02"},
        service_data={"0000fff0-0000-1000-8000-00805f9b34fb": b"sd"},
        service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
        source="local",
        device=BLEDevice(name=name, address=address, details={}),
        advertisement=None,
        connectable=True,
        time=monotonic_time_coarse() if time is None else time,
        tx_power=0,
        raw=None,
    )


def test_to_advertisement_data_translates_fields() -> None:
    """All BluetoothServiceInfoBleak fields map onto AdvertisementData."""
    info = _make_service_info()

    ad = _to_advertisement_data(info)

    assert isinstance(ad, AdvertisementData)
    assert ad.address == info.address
    assert ad.name == info.name
    assert ad.rssi == info.rssi
    assert ad.connectable is True
    assert ad.service_data == dict(info.service_data)
    assert ad.manufacturer_data == dict(info.manufacturer_data)
    assert ad.service_uuids == list(info.service_uuids)


def test_create_matter_ble_proxy_wires_ha_backends(hass: HomeAssistant) -> None:
    """Factory builds MatterBleProxy with HA-backed scan_source and resolver."""
    with patch("homeassistant.components.matter.ble_proxy.MatterBleProxy") as proxy_cls:
        result = create_matter_ble_proxy(hass, "ws://localhost:5580/ble")

    proxy_cls.assert_called_once()
    kwargs = proxy_cls.call_args.kwargs
    assert kwargs["ws_url"] == "ws://localhost:5580/ble"
    assert isinstance(kwargs["scan_source"], HaBluetoothScanSource)
    assert isinstance(kwargs["device_resolver"], HaBluetoothDeviceResolver)
    assert result is proxy_cls.return_value

    coro = MagicMock()
    with patch.object(hass, "async_create_background_task") as bg_task:
        task = kwargs["task_factory"](coro)

    bg_task.assert_called_once_with(coro, name="matter_ble_proxy")
    assert task is bg_task.return_value


async def test_scan_source_start_registers_passive_callback(
    hass: HomeAssistant,
) -> None:
    """start() registers an HA bluetooth callback in PASSIVE scanning mode."""
    source = HaBluetoothScanSource(hass)
    cancel = MagicMock()
    with patch(
        "homeassistant.components.matter.ble_proxy.async_register_callback",
        return_value=cancel,
    ) as register:
        await source.start(MagicMock())

    register.assert_called_once()
    args, _ = register.call_args
    assert args[0] is hass
    assert args[2] is None
    assert args[3] is BluetoothScanningMode.PASSIVE
    assert source._cancel is cancel


async def test_scan_source_start_is_idempotent(hass: HomeAssistant) -> None:
    """A second start() with an existing registration is a no-op."""
    source = HaBluetoothScanSource(hass)
    source._cancel = MagicMock()
    with patch(
        "homeassistant.components.matter.ble_proxy.async_register_callback"
    ) as register:
        await source.start(MagicMock())

    register.assert_not_called()


async def test_scan_source_stop_calls_cancel(hass: HomeAssistant) -> None:
    """stop() invokes the saved cancel callback and clears state."""
    cancel = MagicMock()
    source = HaBluetoothScanSource(hass)
    source._cancel = cancel

    await source.stop()

    cancel.assert_called_once_with()
    assert source._cancel is None


async def test_scan_source_stop_without_start_is_noop(hass: HomeAssistant) -> None:
    """stop() before start() does not raise."""
    await HaBluetoothScanSource(hass).stop()


async def test_scan_source_callback_forwards_advertisement(
    hass: HomeAssistant,
) -> None:
    """The registered HA callback translates and forwards advertisements."""
    forwarded: list[AdvertisementData] = []
    captured: dict[str, object] = {}

    def fake_register(hass_, cb, _matcher, _mode):
        captured["cb"] = cb
        return MagicMock()

    source = HaBluetoothScanSource(hass)
    with patch(
        "homeassistant.components.matter.ble_proxy.async_register_callback",
        side_effect=fake_register,
    ):
        await source.start(forwarded.append)

    captured["cb"](_make_service_info(), object())

    assert len(forwarded) == 1
    assert forwarded[0].address == "AA:BB:CC:DD:EE:FF"


@pytest.mark.parametrize(
    ("advert_time", "expected_count"),
    [
        pytest.param(999.0, 0, id="stale-before-scan-start-dropped"),
        pytest.param(1000.0, 1, id="equal-scan-start-forwarded"),
        pytest.param(1001.0, 1, id="fresh-after-scan-start-forwarded"),
    ],
)
async def test_scan_source_drops_replayed_history(
    hass: HomeAssistant, advert_time: float, expected_count: int
) -> None:
    """Adverts older than the registration instant (HA history replay) are dropped."""
    forwarded: list[AdvertisementData] = []
    captured: dict[str, object] = {}

    def fake_register(hass_, cb, _matcher, _mode):
        captured["cb"] = cb
        return MagicMock()

    source = HaBluetoothScanSource(hass)
    with (
        patch(
            "homeassistant.components.matter.ble_proxy.async_register_callback",
            side_effect=fake_register,
        ),
        patch(
            "homeassistant.components.matter.ble_proxy.MONOTONIC_TIME",
            return_value=1000.0,
        ),
    ):
        await source.start(forwarded.append)

    captured["cb"](_make_service_info(time=advert_time), object())

    assert len(forwarded) == expected_count


async def test_scan_source_callback_swallows_exceptions(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A raising user callback is logged but does not bubble out of HA."""
    captured: dict[str, object] = {}

    def fake_register(hass_, cb, _matcher, _mode):
        captured["cb"] = cb
        return MagicMock()

    def boom(_ad: AdvertisementData) -> None:
        raise RuntimeError("kaboom")

    source = HaBluetoothScanSource(hass)
    with patch(
        "homeassistant.components.matter.ble_proxy.async_register_callback",
        side_effect=fake_register,
    ):
        await source.start(boom)

    captured["cb"](_make_service_info(), object())

    assert "BLE proxy advertisement forward failed" in caplog.text


async def test_device_resolver_delegates_to_ha_bluetooth(
    hass: HomeAssistant,
) -> None:
    """resolve() forwards to async_ble_device_from_address with connectable=True."""
    resolver = HaBluetoothDeviceResolver(hass)
    fake_device = MagicMock()
    with patch(
        "homeassistant.components.matter.ble_proxy.async_ble_device_from_address",
        return_value=fake_device,
    ) as lookup:
        result = await resolver.resolve("AA:BB:CC:DD:EE:FF")

    lookup.assert_called_once_with(hass, "AA:BB:CC:DD:EE:FF", connectable=True)
    assert result is fake_device
