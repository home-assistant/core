"""Tests for the Nespresso Vertuo integration."""

from nespresso_ble import VMiniDevice

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


def make_device() -> VMiniDevice:
    """Return a VMiniDevice with representative live data."""
    return VMiniDevice(
        address=ADDRESS,
        name="VL-MD1_26083MD1p00937820La",
        serial="26083MD1p00937820La",
        firmware_version="4.5.3",
        pairing_status="PAIRED",
        iot_market="NL",
        wifi_mac="80:f1:b2:e1:48:74",
        asset_versions="fmw-main,4.5.3,1.1.0",
        shadow_header="machineStatus,str",
        sensors={
            "machineStatus": "ready",
            "descalingAlert": False,
            "lastCoffeeFamilyID": 255,
            "waterHardness": 4,
            "errorCode": "no error",
            "firstCoffee": False,
            "firstRinsing": False,
            "recipeTag": "unknown",
            "customizationType": "vol and temp",
            "pairing_status": "PAIRED",
        },
    )
