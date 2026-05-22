"""Tests for the Matter integration BLE proxy adapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from matter_ble_proxy import AdvertisementData
import pytest

from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.components.matter.ble_proxy import (
    HaBluetoothDeviceResolver,
    HaBluetoothScanSource,
    _to_advertisement_data,
    create_matter_ble_proxy,
)
from homeassistant.core import HomeAssistant


def _make_service_info() -> MagicMock:
    """Return a stub BluetoothServiceInfoBleak with realistic field values."""
    info = MagicMock()
    info.address = "AA:BB:CC:DD:EE:FF"
    info.name = "TestDevice"
    info.rssi = -55
    info.connectable = True
    info.service_data = {"0000fff0-0000-1000-8000-00805f9b34fb": b"sd"}
    info.manufacturer_data = {0x004C: b"\x01\x02"}
    info.service_uuids = ["0000fff0-0000-1000-8000-00805f9b34fb"]
    return info


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
    assert kwargs["task_factory"] == hass.async_create_task
    assert result is proxy_cls.return_value


async def test_scan_source_start_registers_active_callback(
    hass: HomeAssistant,
) -> None:
    """start() registers an HA bluetooth callback in ACTIVE scanning mode."""
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
    assert args[3] is BluetoothScanningMode.ACTIVE
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
