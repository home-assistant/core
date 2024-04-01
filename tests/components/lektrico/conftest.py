"""Fixtures for Lektrico Charging Station integration tests."""

from ipaddress import ip_address
from unittest.mock import patch

from lektricowifi import Settings

from homeassistant.components.zeroconf import ZeroconfServiceInfo

MOCKED_DEVICE_IP_ADDRESS = "192.168.100.10"
MOCKED_DEVICE_FRIENDLY_NAME = "test"
MOCKED_DEVICE_SERIAL_NUMBER = "500006"
MOCKED_DEVICE_SERIAL_NUMBER_FOR_EM = "810006"
MOCKED_DEVICE_SERIAL_NUMBER_FOR_3EM = "830006"
MOCKED_DEVICE_TYPE = "1p7k"
MOCKED_DEVICE_TYPE_FOR_EM = "em"
MOCKED_DEVICE_TYPE_FOR_3EM = "3em"
MOCKED_DEVICE_BOARD_REV = "B"

MOCKED_DEVICE_ZC_NAME = "Lektrico-1p7k-500006._http._tcp"
MOCKED_DEVICE_ZC_TYPE = "_http._tcp.local."
MOCKED_DEVICE_ZEROCONF_DATA = ZeroconfServiceInfo(
    ip_address=ip_address(MOCKED_DEVICE_IP_ADDRESS),
    ip_addresses=[ip_address(MOCKED_DEVICE_IP_ADDRESS)],
    hostname=f"{MOCKED_DEVICE_ZC_NAME.lower()}.local.",
    port=80,
    type=MOCKED_DEVICE_ZC_TYPE,
    name=MOCKED_DEVICE_ZC_NAME,
    properties={
        "id": "1p7k_500006",
        "fw_id": "20230109-124642/v1.22-36-g56a3edd-develop-dirty",
    },
)

MOCKED_DEVICE_ZEROCONF_DATA_FOR_EM = ZeroconfServiceInfo(
    ip_address=ip_address(MOCKED_DEVICE_IP_ADDRESS),
    ip_addresses=[ip_address(MOCKED_DEVICE_IP_ADDRESS)],
    hostname=f"{MOCKED_DEVICE_ZC_NAME.lower()}.local.",
    port=80,
    type=MOCKED_DEVICE_ZC_TYPE,
    name=MOCKED_DEVICE_ZC_NAME,
    properties={
        "id": "m2w_810006",
        "fw_id": "20230109-124642/v1.22-36-g56a3edd-develop-dirty",
    },
)

MOCKED_DEVICE_ZEROCONF_DATA_FOR_3EM = ZeroconfServiceInfo(
    ip_address=ip_address(MOCKED_DEVICE_IP_ADDRESS),
    ip_addresses=[ip_address(MOCKED_DEVICE_IP_ADDRESS)],
    hostname=f"{MOCKED_DEVICE_ZC_NAME.lower()}.local.",
    port=80,
    type=MOCKED_DEVICE_ZC_TYPE,
    name=MOCKED_DEVICE_ZC_NAME,
    properties={
        "id": "m2w_830006",
        "fw_id": "20230109-124642/v1.22-36-g56a3edd-develop-dirty",
    },
)

MOCKED_DEVICE_BAD_ID_ZEROCONF_DATA = ZeroconfServiceInfo(
    ip_address=ip_address(MOCKED_DEVICE_IP_ADDRESS),
    ip_addresses=[ip_address(MOCKED_DEVICE_IP_ADDRESS)],
    hostname=f"{MOCKED_DEVICE_ZC_NAME.lower()}.local.",
    port=80,
    type=MOCKED_DEVICE_ZC_TYPE,
    name=MOCKED_DEVICE_ZC_NAME,
    properties={
        "id": "500006",
        "fw_id": "20230109-124642/v1.22-36-g56a3edd-develop-dirty",
    },
)

MOCKED_DEVICE_BAD_NO_ID_ZEROCONF_DATA = ZeroconfServiceInfo(
    ip_address=ip_address(MOCKED_DEVICE_IP_ADDRESS),
    ip_addresses=[ip_address(MOCKED_DEVICE_IP_ADDRESS)],
    hostname=f"{MOCKED_DEVICE_ZC_NAME.lower()}.local.",
    port=80,
    type=MOCKED_DEVICE_ZC_TYPE,
    name=MOCKED_DEVICE_ZC_NAME,
    properties={"fw_id": "20230109-124642/v1.22-36-g56a3edd-develop-dirty"},
)


def _mocked_device_config() -> Settings:
    return Settings(
        type=MOCKED_DEVICE_TYPE,
        serial_number=MOCKED_DEVICE_SERIAL_NUMBER,
        board_revision=MOCKED_DEVICE_BOARD_REV,
    )


def _patch_device_config(device=None, exception=None):
    async def _device_config(*args, **kwargs):
        if exception:
            raise exception
        return _mocked_device_config()

    return patch(
        "homeassistant.components.lektrico.config_flow.Device.device_config",
        new=_device_config,
    )
