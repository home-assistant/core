"""Bluetooth helper tests for Inepro Metering."""

from types import SimpleNamespace
from unittest.mock import patch

from homeassistant.components.inepro_metering.bluetooth import (
    async_discover_grow_bluetooth_meters,
    async_entry_data_with_ha_ble_device,
    grow_bluetooth_meter_from_service_info,
)
from homeassistant.components.inepro_metering.const import (
    CONF_BLUETOOTH_ADDRESS,
    CONF_BLUETOOTH_NAME,
    CONF_TRANSPORT,
    TransportType,
)
from homeassistant.components.inepro_metering.modbus import (
    BLUETOOTH_PAIRING_MODE_NEVER,
    CONF_BLUETOOTH_FORCE_REPAIR,
    CONF_BLUETOOTH_PAIRING_MODE,
)


def test_grow_bluetooth_meter_from_service_info_returns_library_model() -> None:
    """The HA adapter should translate one Bluetooth advertisement into the shared model."""
    meter = grow_bluetooth_meter_from_service_info(
        SimpleNamespace(
            name="IM-075625480002",
            address="80:F1:B2:58:DD:5A",
            rssi=-88,
        )
    )

    assert meter is not None
    assert meter.serial_number == "075625480002"
    assert meter.variant == "grow_750"
    assert meter.address == "80:F1:B2:58:DD:5A"
    assert meter.transport is TransportType.BLUETOOTH


def test_grow_bluetooth_meter_from_service_info_rejects_unknown_names() -> None:
    """Unrecognized Bluetooth advertisements should stay out of the HA flow."""
    meter = grow_bluetooth_meter_from_service_info(
        SimpleNamespace(
            name="Unknown meter",
            address="80:F1:B2:58:DD:5A",
            rssi=-88,
        )
    )

    assert meter is None


def test_async_discover_grow_bluetooth_meters_prefers_strongest_rssi(hass) -> None:
    """The HA adapter should deduplicate cache hits by serial number and keep the best RSSI."""
    service_infos = [
        SimpleNamespace(
            name="IM-075625480002",
            address="80:F1:B2:58:DD:5A",
            rssi=-88,
        ),
        SimpleNamespace(
            name="IM-075625480002",
            address="80:F1:B2:58:DD:5B",
            rssi=-61,
        ),
        SimpleNamespace(
            name="IM-085125250008",
            address="80:F1:B2:58:DD:5C",
            rssi=-73,
        ),
        SimpleNamespace(
            name="Unknown meter",
            address="80:F1:B2:58:DD:5D",
            rssi=-10,
        ),
    ]

    with patch(
        "homeassistant.components.bluetooth.async_discovered_service_info",
        return_value=service_infos,
    ):
        meters = async_discover_grow_bluetooth_meters(hass)

    assert [meter.serial_number for meter in meters] == [
        "075625480002",
        "085125250008",
    ]
    assert meters[0].address == "80:F1:B2:58:DD:5B"
    assert meters[0].transport is TransportType.BLUETOOTH


def test_entry_data_uses_pairing_never_by_default(hass) -> None:
    """Normal setup and runtime validation should not start pairing in HA."""
    ble_device = SimpleNamespace(name="IM-075625480002", address="80:F1:B2:58:DD:5A")
    entry_data = {
        CONF_TRANSPORT: TransportType.BLUETOOTH.value,
        CONF_BLUETOOTH_ADDRESS: "80:F1:B2:58:DD:5A",
        CONF_BLUETOOTH_NAME: "IM-075625480002",
    }

    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=ble_device,
    ):
        validation_data = async_entry_data_with_ha_ble_device(
            hass,
            entry_data,
            require_device=True,
        )
        runtime_data = async_entry_data_with_ha_ble_device(
            hass,
            entry_data,
            require_device=False,
        )
        gatt_data = async_entry_data_with_ha_ble_device(
            hass,
            entry_data,
            pairing_mode=None,
        )

    assert validation_data[CONF_BLUETOOTH_PAIRING_MODE] == BLUETOOTH_PAIRING_MODE_NEVER
    assert runtime_data[CONF_BLUETOOTH_PAIRING_MODE] == BLUETOOTH_PAIRING_MODE_NEVER
    assert CONF_BLUETOOTH_PAIRING_MODE not in gatt_data
    assert CONF_BLUETOOTH_FORCE_REPAIR not in gatt_data
