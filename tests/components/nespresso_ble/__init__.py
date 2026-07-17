"""Tests for the Nespresso integration."""

from nespresso_ble import (
    MachineFamily,
    MachineStatus,
    NespressoDevice,
    PairingStatus,
    WaterHardness,
)

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

VMINI_SERVICE_UUID = "96600100-526e-4676-a11a-af1eb848165b"
ADDRESS = "80:F1:B2:E1:48:76"


def make_service_info(
    address: str = ADDRESS,
    name: str = "VL-MD1_26083MD1p00937820La",
) -> BluetoothServiceInfoBleak:
    """Return a BluetoothServiceInfoBleak for a VMini machine."""
    return BluetoothServiceInfoBleak(
        name=name,
        address=address,
        device=generate_ble_device(address=address, name=name),
        rssi=-65,
        manufacturer_data={549: bytes.fromhex("80f1b2e14876")},
        service_data={},
        service_uuids=[VMINI_SERVICE_UUID],
        source="local",
        advertisement=generate_advertisement_data(
            local_name=name,
            service_uuids=[VMINI_SERVICE_UUID],
        ),
        connectable=True,
        time=0,
        tx_power=0,
    )


SERVICE_INFO = make_service_info()

NOT_NESPRESSO_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="unknown",
    address="00:cc:cc:cc:cc:cc",
    device=generate_ble_device(address="00:cc:cc:cc:cc:cc", name="unknown"),
    rssi=-65,
    manufacturer_data={},
    service_data={},
    service_uuids=[],
    source="local",
    advertisement=generate_advertisement_data(manufacturer_data={}, service_uuids=[]),
    connectable=True,
    time=0,
    tx_power=0,
)


def make_device() -> NespressoDevice:
    """Return a typed NespressoDevice with representative live VMini data."""
    return NespressoDevice(
        address=ADDRESS,
        name="VL-MD1_26083MD1p00937820La",
        family=MachineFamily.VMINI,
        serial="26083MD1p00937820La",
        firmware_version="4.5.3",
        pairing_status=PairingStatus.PAIRED,
        iot_market="NL",
        wifi_mac="80:f1:b2:e1:48:74",
        status=MachineStatus.READY,
        error=False,
        error_code="no error",
        water_hardness=WaterHardness.LEVEL_4,
        descaling_needed=False,
    )
