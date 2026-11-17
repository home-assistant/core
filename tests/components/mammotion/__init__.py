"""Tests for the Mammotion integration."""

from pymammotion.aliyun.model.dev_by_account_response import Device
from pymammotion.http.model.http import LoginResponseData
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

DEFAULT_NAME = "Luba-ABC123"
DEFAULT_ADDRESS = "AA:BB:CC:DD:EE:FF"
DEFAULT_MAC = "aa:bb:cc:dd:ee:ff"
ACCOUNT_NAME = "user@example.com"
ACCOUNT_ID = "user123"

SERVICE_UUID = "0000ffff-0000-1000-8000-00805f9b34fb"

LOGIN_INFO = LoginResponseData.from_dict(
    {
        "access_token": "access",
        "token_type": "bearer",
        "refresh_token": "refresh",
        "expires_in": 3600,
        "authorization_code": "code",
        "userInformation": {
            "areaCode": "NZ",
            "domainAbbreviation": "AU",
            "userId": "1",
            "userAccount": ACCOUNT_ID,
            "authType": "0",
        },
    }
)

OTHER_LOGIN_INFO = LoginResponseData.from_dict(
    {
        **LOGIN_INFO.to_dict(),
        "userInformation": {
            **LOGIN_INFO.userInformation.to_dict(),
            "userAccount": "other_user",
        },
    }
)


def service_info(name: str, address: str) -> BluetoothServiceInfo:
    """Return the advertisement of a Mammotion mower."""
    return BluetoothServiceInfo(
        name=name,
        address=address,
        rssi=-60,
        manufacturer_data={},
        service_uuids=[SERVICE_UUID],
        service_data={},
        source="local",
    )


LUBA_SERVICE_INFO = service_info(DEFAULT_NAME, DEFAULT_ADDRESS)


def cloud_device(device_name: str = DEFAULT_NAME) -> Device:
    """Return a device as the cloud lists it for the account."""
    return Device(
        gmt_modified=0,
        node_type="DEVICE",
        device_name=device_name,
        product_name="Luba 2",
        status=1,
        identity_id="identity",
        net_type="NET_WIFI",
        category_key="LawnMower",
        product_key="product",
        is_edge_gateway=False,
        category_name="Lawn mower",
        identity_alias="alias",
        iot_id="iot",
        bind_time=0,
        owned=1,
        thing_type="DEVICE",
        nick_name="Luba",
        product_model="Luba 2 AWD",
    )


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the Mammotion integration for testing."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
