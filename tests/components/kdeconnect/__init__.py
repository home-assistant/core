"""Tests for the KDEConnect integration."""
from unittest.mock import AsyncMock, MagicMock

from pykdeconnect.const import KdeConnectDeviceType

EXAMPLE_DEVICE_NAME = "Device 1"
EXAMPLE_DEVICE_ID = "device_1"
EXAMPLE_DEVICE_TYPE = KdeConnectDeviceType.PHONE
EXAMPLE_DEVICE_OUT_CAPS = ["example_cap_1"]
EXAMPLE_DEVICE_IN_CAPS = ["example_cap_2"]
EXAMPLE_DEVICE_CERT = "foo"


def _create_mocked_device(pairing_result):
    device = MagicMock()
    device.device_name = EXAMPLE_DEVICE_NAME
    device.device_id = EXAMPLE_DEVICE_ID
    device.device_type = EXAMPLE_DEVICE_TYPE
    device.incoming_capabilities = EXAMPLE_DEVICE_IN_CAPS
    device.outgoing_capabilities = EXAMPLE_DEVICE_OUT_CAPS

    device.certificate.public_bytes.return_value = EXAMPLE_DEVICE_CERT.encode()

    device.pair = AsyncMock(return_value=pairing_result)

    return device


def _create_mocked_client(devices):
    client = MagicMock()

    client.connected_devices = {d.device_id: d for d in devices}
    client.advertise_once = AsyncMock()

    return client
