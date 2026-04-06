"""Tests for the Bluetooth helpers of Connectivity Monitor."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.connectivity_monitor.bluetooth import (
    _merge_device,
    _normalize_address,
    async_get_bluetooth_device_active,
    async_get_bluetooth_device_details,
    async_get_bluetooth_devices,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

# ──────────────────────────────────────────────────────────────────────────────
# Pure helpers
# ──────────────────────────────────────────────────────────────────────────────


def test_normalize_address_upper() -> None:
    """_normalize_address uppercases and strips None."""
    assert _normalize_address("aa:bb:cc:dd:ee:ff") == "AA:BB:CC:DD:EE:FF"


def test_normalize_address_none() -> None:
    """_normalize_address returns empty string for None."""
    assert _normalize_address(None) == ""


def test_normalize_address_already_upper() -> None:
    """_normalize_address is idempotent on uppercase input."""
    assert _normalize_address("AA:BB:CC:DD:EE:FF") == "AA:BB:CC:DD:EE:FF"


def test_merge_device_prefers_new_values() -> None:
    """_merge_device replaces existing with non-empty update values."""
    base = {"bt_address": "AA:BB:CC", "name": "old"}
    update = {"bt_address": "AA:BB:CC", "name": "new"}
    result = _merge_device(base, update)
    assert result["name"] == "new"


def test_merge_device_skips_empty_values() -> None:
    """_merge_device keeps existing values when update value is empty."""
    base = {"bt_address": "AA:BB:CC", "name": "keeps"}
    update = {"bt_address": "AA:BB:CC", "name": None}
    result = _merge_device(base, update)
    assert result["name"] == "keeps"


def test_merge_device_skips_empty_string() -> None:
    """_merge_device keeps existing value when update is empty string."""
    base = {"bt_address": "AA:BB:CC", "name": "keeps"}
    update = {"bt_address": "AA:BB:CC", "name": ""}
    result = _merge_device(base, update)
    assert result["name"] == "keeps"


def test_merge_device_rssi_prefers_higher() -> None:
    """_merge_device RSSI: keeps the higher (less negative) value."""
    base = {"rssi": -80}
    update = {"rssi": -60}
    result = _merge_device(base, update)
    assert result["rssi"] == -60


def test_merge_device_rssi_keeps_existing_when_lower_update() -> None:
    """_merge_device RSSI: keeps existing when update value is weaker."""
    base = {"rssi": -50}
    update = {"rssi": -90}
    result = _merge_device(base, update)
    assert result["rssi"] == -50


def test_merge_device_rssi_none_base() -> None:
    """_merge_device RSSI: uses update value when base is None."""
    base = {"rssi": None}
    update = {"rssi": -70}
    result = _merge_device(base, update)
    assert result["rssi"] == -70


# ──────────────────────────────────────────────────────────────────────────────
# async_get_bluetooth_devices
# ──────────────────────────────────────────────────────────────────────────────


async def test_get_bluetooth_devices_empty(hass: HomeAssistant) -> None:
    """Returns empty list when no Bluetooth discoveries and no registry devices."""
    with patch(
        "homeassistant.components.connectivity_monitor.bluetooth.bluetooth.async_discovered_service_info",
        return_value=[],
    ):
        devices = await async_get_bluetooth_devices(hass)
    assert devices == []


async def test_get_bluetooth_devices_from_service_info(hass: HomeAssistant) -> None:
    """Returns device info built from BLE advertisement data."""
    service_info = MagicMock()
    service_info.address = "AA:BB:CC:DD:EE:FF"
    service_info.name = "My BLE Device"
    service_info.rssi = -70
    service_info.source = "source1"
    service_info.connectable = True
    service_info.service_uuids = ["0000180f-0000-1000-8000-00805f9b34fb"]
    service_info.manufacturer_data = {76: b"\x01\x02"}
    service_info.service_data = {}

    with patch(
        "homeassistant.components.connectivity_monitor.bluetooth.bluetooth.async_discovered_service_info",
        return_value=[service_info],
    ):
        devices = await async_get_bluetooth_devices(hass)

    assert len(devices) == 1
    assert devices[0]["bt_address"] == "AA:BB:CC:DD:EE:FF"
    assert devices[0]["name"] == "My BLE Device"
    assert devices[0]["rssi"] == -70


async def test_get_bluetooth_devices_skips_empty_address(hass: HomeAssistant) -> None:
    """Service info with no address is silently skipped."""
    service_info = MagicMock()
    service_info.address = None

    with patch(
        "homeassistant.components.connectivity_monitor.bluetooth.bluetooth.async_discovered_service_info",
        return_value=[service_info],
    ):
        devices = await async_get_bluetooth_devices(hass)

    assert devices == []


async def test_get_bluetooth_devices_merges_registry(hass: HomeAssistant) -> None:
    """Registry device data is merged into service-info-based entry."""
    service_info = MagicMock()
    service_info.address = "AA:BB:CC:DD:EE:FF"
    service_info.name = "BLE Name"
    service_info.rssi = -80
    service_info.source = "s"
    service_info.connectable = False
    service_info.service_uuids = []
    service_info.manufacturer_data = {}
    service_info.service_data = {}

    # Register a config entry and device in the device registry
    bt_entry = MockConfigEntry(domain="bluetooth", entry_id="test_entry")
    bt_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id="test_entry",
        identifiers={("bluetooth", "AA:BB:CC:DD:EE:FF")},
        name="Registry Name",
        manufacturer="ACME",
        model="V1",
    )

    with patch(
        "homeassistant.components.connectivity_monitor.bluetooth.bluetooth.async_discovered_service_info",
        return_value=[service_info],
    ):
        devices = await async_get_bluetooth_devices(hass)

    assert len(devices) == 1
    # Registry enriches with manufacturer and device_id
    assert devices[0]["manufacturer"] == "ACME"
    assert devices[0]["device_id"] == device_entry.id


async def test_get_bluetooth_devices_registry_only(hass: HomeAssistant) -> None:
    """Devices with only a registry entry (no service info) are included."""
    bt_entry2 = MockConfigEntry(domain="bluetooth", entry_id="test_entry2")
    bt_entry2.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id="test_entry2",
        identifiers={("bluetooth", "11:22:33:44:55:66")},
        name="Registry-only BT device",
    )

    with patch(
        "homeassistant.components.connectivity_monitor.bluetooth.bluetooth.async_discovered_service_info",
        return_value=[],
    ):
        devices = await async_get_bluetooth_devices(hass)

    assert any(d["bt_address"] == "11:22:33:44:55:66" for d in devices)


async def test_get_bluetooth_devices_error(hass: HomeAssistant) -> None:
    """When bluetooth raises AttributeError we return empty list."""
    with patch(
        "homeassistant.components.connectivity_monitor.bluetooth.bluetooth.async_discovered_service_info",
        side_effect=AttributeError("boom"),
    ):
        devices = await async_get_bluetooth_devices(hass)

    assert devices == []


async def test_get_bluetooth_devices_sorted(hass: HomeAssistant) -> None:
    """Returned list is sorted by device name (case-insensitive)."""
    svc_z = MagicMock()
    svc_z.address = "AA:00:00:00:00:01"
    svc_z.name = "ZZZ Device"
    svc_z.rssi = -70
    svc_z.source = "s"
    svc_z.connectable = True
    svc_z.service_uuids = []
    svc_z.manufacturer_data = {}
    svc_z.service_data = {}

    svc_a = MagicMock()
    svc_a.address = "AA:00:00:00:00:02"
    svc_a.name = "AAA Device"
    svc_a.rssi = -70
    svc_a.source = "s"
    svc_a.connectable = True
    svc_a.service_uuids = []
    svc_a.manufacturer_data = {}
    svc_a.service_data = {}

    with patch(
        "homeassistant.components.connectivity_monitor.bluetooth.bluetooth.async_discovered_service_info",
        return_value=[svc_z, svc_a],
    ):
        devices = await async_get_bluetooth_devices(hass)

    assert devices[0]["name"] == "AAA Device"
    assert devices[1]["name"] == "ZZZ Device"


# ──────────────────────────────────────────────────────────────────────────────
# async_get_bluetooth_device_active
# ──────────────────────────────────────────────────────────────────────────────


async def test_get_bluetooth_device_active_found_non_connectable(
    hass: HomeAssistant,
) -> None:
    """Returns True when device is present (non-connectable scan)."""
    mock_service_info = MagicMock()

    with (
        patch(
            "homeassistant.components.connectivity_monitor.bluetooth.bluetooth.async_last_service_info",
            return_value=mock_service_info,
        ),
        patch(
            "homeassistant.components.connectivity_monitor.bluetooth.bluetooth.async_address_present",
            return_value=True,
        ),
    ):
        result = await async_get_bluetooth_device_active(hass, "AA:BB:CC:DD:EE:FF")

    assert result is True


async def test_get_bluetooth_device_active_found_connectable(
    hass: HomeAssistant,
) -> None:
    """Returns True when device is found via connectable=True fallback."""
    mock_service_info = MagicMock()

    def _last_service_info(h, address, connectable):
        if connectable is False:
            return None
        return mock_service_info

    with (
        patch(
            "homeassistant.components.connectivity_monitor.bluetooth.bluetooth.async_last_service_info",
            side_effect=_last_service_info,
        ),
        patch(
            "homeassistant.components.connectivity_monitor.bluetooth.bluetooth.async_address_present",
            return_value=True,
        ),
    ):
        result = await async_get_bluetooth_device_active(hass, "aa:bb:cc:dd:ee:ff")

    assert result is True


async def test_get_bluetooth_device_active_not_found(hass: HomeAssistant) -> None:
    """Returns None when service info is not found for the address."""
    with patch(
        "homeassistant.components.connectivity_monitor.bluetooth.bluetooth.async_last_service_info",
        return_value=None,
    ):
        result = await async_get_bluetooth_device_active(hass, "AA:BB:CC:DD:EE:FF")

    assert result is None


async def test_get_bluetooth_device_active_error(hass: HomeAssistant) -> None:
    """Returns None and logs warning on AttributeError."""
    with patch(
        "homeassistant.components.connectivity_monitor.bluetooth.bluetooth.async_last_service_info",
        side_effect=AttributeError("boom"),
    ):
        result = await async_get_bluetooth_device_active(hass, "AA:BB:CC:DD:EE:FF")

    assert result is None


async def test_get_bluetooth_device_active_runtime_error(hass: HomeAssistant) -> None:
    """Returns None and logs warning on RuntimeError."""
    with patch(
        "homeassistant.components.connectivity_monitor.bluetooth.bluetooth.async_last_service_info",
        side_effect=RuntimeError("boom"),
    ):
        result = await async_get_bluetooth_device_active(hass, "AA:BB:CC:DD:EE:FF")

    assert result is None


# ──────────────────────────────────────────────────────────────────────────────
# async_get_bluetooth_device_details
# ──────────────────────────────────────────────────────────────────────────────


async def test_get_bluetooth_device_details_not_found(hass: HomeAssistant) -> None:
    """Returns inactive dict when no service info available."""
    with patch(
        "homeassistant.components.connectivity_monitor.bluetooth.bluetooth.async_last_service_info",
        return_value=None,
    ):
        result = await async_get_bluetooth_device_details(hass, "AA:BB:CC:DD:EE:FF")

    assert result["active"] is False
    assert result["device_found"] is False


async def test_get_bluetooth_device_details_found(hass: HomeAssistant) -> None:
    """Returns full details dict when service info is present."""
    svc = MagicMock()
    svc.name = "Detail Device"
    svc.rssi = -65
    svc.source = "src"
    svc.connectable = True
    svc.service_uuids = []
    svc.manufacturer_data = {}
    svc.service_data = {}
    svc.time = 12345.0
    svc.tx_power = 10

    with (
        patch(
            "homeassistant.components.connectivity_monitor.bluetooth.bluetooth.async_last_service_info",
            return_value=svc,
        ),
        patch(
            "homeassistant.components.connectivity_monitor.bluetooth.bluetooth.async_address_present",
            return_value=True,
        ),
    ):
        result = await async_get_bluetooth_device_details(hass, "AA:BB:CC:DD:EE:FF")

    assert result["device_found"] is True
    assert result["active"] is True
    assert result["name"] == "Detail Device"
    assert result["rssi"] == -65
    assert result["tx_power"] == 10


async def test_get_bluetooth_device_details_connectable_fallback(
    hass: HomeAssistant,
) -> None:
    """Falls back to connectable=True lookup when non-connectable returns None."""
    svc = MagicMock()
    svc.name = "CB Device"
    svc.rssi = -70
    svc.source = "src"
    svc.connectable = True
    svc.service_uuids = []
    svc.manufacturer_data = {}
    svc.service_data = {}
    svc.time = None
    svc.tx_power = None

    def _last_service_info(h, address, connectable):
        if connectable is False:
            return None
        return svc

    with (
        patch(
            "homeassistant.components.connectivity_monitor.bluetooth.bluetooth.async_last_service_info",
            side_effect=_last_service_info,
        ),
        patch(
            "homeassistant.components.connectivity_monitor.bluetooth.bluetooth.async_address_present",
            return_value=False,
        ),
    ):
        result = await async_get_bluetooth_device_details(hass, "aa:bb:cc:dd:ee:ff")

    assert result["device_found"] is True
    assert result["active"] is False


async def test_get_bluetooth_device_details_error(hass: HomeAssistant) -> None:
    """Returns inactive dict on AttributeError."""
    with patch(
        "homeassistant.components.connectivity_monitor.bluetooth.bluetooth.async_last_service_info",
        side_effect=AttributeError("err"),
    ):
        result = await async_get_bluetooth_device_details(hass, "AA:BB:CC:DD:EE:FF")

    assert result["active"] is False
