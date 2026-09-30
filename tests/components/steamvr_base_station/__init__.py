"""Tests for the SteamVR Base Station integration."""

import time

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

TEST_ADDRESS = "AA:BB:CC:DD:EE:01"
TEST_NAME = "LHB-747A9BC5"
VALVE_COMPANY_ID = 1373


def payload(power: int = 0x0B, channel: int = 1, fault: int = 0) -> bytes:
    """Build a V2 advertisement payload in the layout real stations send."""
    return bytes([0x00, 0x02, channel, 0x01, power, 0x06, fault])


def make_service_info(
    data: bytes | None = None,
    *,
    name: str = TEST_NAME,
    address: str = TEST_ADDRESS,
) -> BluetoothServiceInfoBleak:
    """Build a service info as the bluetooth integration would deliver it."""
    manufacturer_data = {VALVE_COMPANY_ID: payload() if data is None else data}
    return BluetoothServiceInfoBleak(
        name=name,
        address=address,
        rssi=-60,
        manufacturer_data=manufacturer_data,
        service_data={},
        service_uuids=[],
        source="local",
        device=generate_ble_device(address, name),
        advertisement=generate_advertisement_data(
            local_name=name, manufacturer_data=manufacturer_data
        ),
        connectable=True,
        time=time.monotonic(),
        tx_power=-127,
    )


STATION_SERVICE_INFO = make_service_info()
