"""Test the Xiaomi Miio config flow."""
from ipaddress import ip_address
from unittest.mock import Mock, patch

from construct.core import ChecksumError
from micloud.micloudexception import MiCloudAccessDenied
from miio import DeviceException
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import zeroconf
from homeassistant.components.xiaomi_miio import const
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_TOKEN
from homeassistant.core import HomeAssistant

from . import TEST_MAC

from tests.common import MockConfigEntry

ZEROCONF_NAME = "name"
ZEROCONF_PROP = "properties"
ZEROCONF_MAC = "mac"

TEST_HOST = "1.2.3.4"
TEST_HOST2 = "5.6.7.8"
TEST_CLOUD_USER = "username"
TEST_CLOUD_PASS = "password"
TEST_CLOUD_COUNTRY = "cn"
TEST_TOKEN = "12345678901234567890123456789012"
TEST_NAME = "Test_Gateway"
TEST_NAME2 = "Test_Gateway_2"
TEST_MODEL = const.MODELS_GATEWAY[0]
TEST_MAC2 = "mn:op:qr:st:uv:wx"
TEST_MAC_DEVICE = "abcdefghijkl"
TEST_MAC_DEVICE2 = "mnopqrstuvwx"
TEST_GATEWAY_ID = TEST_MAC
TEST_HARDWARE_VERSION = "AB123"
TEST_FIRMWARE_VERSION = "1.2.3_456"
TEST_ZEROCONF_NAME = "lumi-gateway-v3_miio12345678._miio._udp.local."
TEST_CLOUD_DEVICES_1 = [
    {
        "parent_id": None,
        "name": TEST_NAME,
        "model": TEST_MODEL,
        "localip": TEST_HOST,
        "mac": TEST_MAC_DEVICE,
        "token": TEST_TOKEN,
    }
]
TEST_CLOUD_DEVICES_2 = [
    {
        "parent_id": None,
        "name": TEST_NAME,
        "model": TEST_MODEL,
        "localip": TEST_HOST,
        "mac": TEST_MAC_DEVICE,
        "token": TEST_TOKEN,
    },
    {
        "parent_id": None,
        "name": TEST_NAME2,
        "model": TEST_MODEL,
        "localip": TEST_HOST2,
        "mac": TEST_MAC_DEVICE2,
        "token": TEST_TOKEN,
    },
]


@pytest.fixture(name="xiaomi_miio_connect", autouse=True)
def xiaomi_miio_connect_fixture():
    """Mock miio connection and entry setup."""
    mock_info = get_mock_info()

    with patch(
        "homeassistant.components.xiaomi_miio.device.Device.info",
        return_value=mock_info,
    ), patch(
        "homeassistant.components.xiaomi_miio.config_flow.MiCloud.login",
        return_value=True,
    ), patch(
        "homeassistant.components.xiaomi_miio.config_flow.MiCloud.get_devices",
        return_value=TEST_CLOUD_DEVICES_1,
    ), patch(
        "homeassistant.components.xiaomi_miio.async_setup_entry", return_value=True
    ), patch(
        "homeassistant.components.xiaomi_miio.async_unload_entry", return_value=True
    ):
        yield


def get_mock_info(
    model=TEST_MODEL,
    mac_address=TEST_MAC,
    hardware_version=TEST_HARDWARE_VERSION,
    firmware_version=TEST_FIRMWARE_VERSION,
):
    """Return a mock gateway info instance."""
    gateway_info = Mock()
    gateway_info.model = model
    gateway_info.mac_address = mac_address
    gateway_info.hardware_version = hardware_version
    gateway_info.firmware_version = firmware_version

    return gateway_info


async def test_config_flow_step_gateway_connect_error(hass: HomeAssistant) -> None:
    """Test config flow, gateway connection error."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "cloud"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_MANUAL: True},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "manual"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.xiaomi_miio.device.Device.info",
        side_effect=DeviceException({}),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: TEST_HOST, CONF_TOKEN: TEST_TOKEN},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "connect"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_config_flow_gateway_success(hass: HomeAssistant) -> None:
    """Test a successful config flow."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "cloud"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_MANUAL: True},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "manual"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: TEST_HOST, CONF_TOKEN: TEST_TOKEN},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_MODEL
    assert result["data"] == {
        const.CONF_FLOW_TYPE: const.CONF_GATEWAY,
        const.CONF_CLOUD_USERNAME: None,
        const.CONF_CLOUD_PASSWORD: None,
        const.CONF_CLOUD_COUNTRY: None,
        CONF_HOST: TEST_HOST,
        CONF_TOKEN: TEST_TOKEN,
        CONF_MODEL: TEST_MODEL,
        const.CONF_MAC: TEST_MAC,
    }


async def test_config_flow_gateway_cloud_success(hass: HomeAssistant) -> None:
    """Test a successful config flow using cloud."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "cloud"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            const.CONF_CLOUD_USERNAME: TEST_CLOUD_USER,
            const.CONF_CLOUD_PASSWORD: TEST_CLOUD_PASS,
            const.CONF_CLOUD_COUNTRY: TEST_CLOUD_COUNTRY,
        },
    )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        const.CONF_FLOW_TYPE: const.CONF_GATEWAY,
        const.CONF_CLOUD_USERNAME: TEST_CLOUD_USER,
        const.CONF_CLOUD_PASSWORD: TEST_CLOUD_PASS,
        const.CONF_CLOUD_COUNTRY: TEST_CLOUD_COUNTRY,
        CONF_HOST: TEST_HOST,
        CONF_TOKEN: TEST_TOKEN,
        CONF_MODEL: TEST_MODEL,
        const.CONF_MAC: TEST_MAC,
    }


async def test_config_flow_gateway_cloud_multiple_success(hass: HomeAssistant) -> None:
    """Test a successful config flow using cloud with multiple devices."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "cloud"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.xiaomi_miio.config_flow.MiCloud.get_devices",
        return_value=TEST_CLOUD_DEVICES_2,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                const.CONF_CLOUD_USERNAME: TEST_CLOUD_USER,
                const.CONF_CLOUD_PASSWORD: TEST_CLOUD_PASS,
                const.CONF_CLOUD_COUNTRY: TEST_CLOUD_COUNTRY,
            },
        )

    assert result["type"] == "form"
    assert result["step_id"] == "select"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"select_device": f"{TEST_NAME2} - {TEST_MODEL}"},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME2
    assert result["data"] == {
        const.CONF_FLOW_TYPE: const.CONF_GATEWAY,
        const.CONF_CLOUD_USERNAME: TEST_CLOUD_USER,
        const.CONF_CLOUD_PASSWORD: TEST_CLOUD_PASS,
        const.CONF_CLOUD_COUNTRY: TEST_CLOUD_COUNTRY,
        CONF_HOST: TEST_HOST2,
        CONF_TOKEN: TEST_TOKEN,
        CONF_MODEL: TEST_MODEL,
        const.CONF_MAC: TEST_MAC2,
    }


async def test_config_flow_gateway_cloud_incomplete(hass: HomeAssistant) -> None:
    """Test a failed config flow using incomplete cloud credentials."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "cloud"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            const.CONF_CLOUD_USERNAME: TEST_CLOUD_USER,
            const.CONF_CLOUD_COUNTRY: TEST_CLOUD_COUNTRY,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "cloud"
    assert result["errors"] == {"base": "cloud_credentials_incomplete"}


async def test_config_flow_gateway_cloud_login_error(hass: HomeAssistant) -> None:
    """Test a failed config flow using cloud login error."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "cloud"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.xiaomi_miio.config_flow.MiCloud.login",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                const.CONF_CLOUD_USERNAME: TEST_CLOUD_USER,
                const.CONF_CLOUD_PASSWORD: TEST_CLOUD_PASS,
                const.CONF_CLOUD_COUNTRY: TEST_CLOUD_COUNTRY,
            },
        )

    assert result["type"] == "form"
    assert result["step_id"] == "cloud"
    assert result["errors"] == {"base": "cloud_login_error"}

    with patch(
        "homeassistant.components.xiaomi_miio.config_flow.MiCloud.login",
        side_effect=MiCloudAccessDenied({}),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                const.CONF_CLOUD_USERNAME: TEST_CLOUD_USER,
                const.CONF_CLOUD_PASSWORD: TEST_CLOUD_PASS,
                const.CONF_CLOUD_COUNTRY: TEST_CLOUD_COUNTRY,
            },
        )

    assert result["type"] == "form"
    assert result["step_id"] == "cloud"
    assert result["errors"] == {"base": "cloud_login_error"}

    with patch(
        "homeassistant.components.xiaomi_miio.config_flow.MiCloud.login",
        side_effect=Exception({}),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                const.CONF_CLOUD_USERNAME: TEST_CLOUD_USER,
                const.CONF_CLOUD_PASSWORD: TEST_CLOUD_PASS,
                const.CONF_CLOUD_COUNTRY: TEST_CLOUD_COUNTRY,
            },
        )

    assert result["type"] == "abort"
    assert result["reason"] == "unknown"


async def test_config_flow_gateway_cloud_no_devices(hass: HomeAssistant) -> None:
    """Test a failed config flow using cloud with no devices."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "cloud"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.xiaomi_miio.config_flow.MiCloud.get_devices",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                const.CONF_CLOUD_USERNAME: TEST_CLOUD_USER,
                const.CONF_CLOUD_PASSWORD: TEST_CLOUD_PASS,
                const.CONF_CLOUD_COUNTRY: TEST_CLOUD_COUNTRY,
            },
        )

    assert result["type"] == "form"
    assert result["step_id"] == "cloud"
    assert result["errors"] == {"base": "cloud_no_devices"}

    with patch(
        "homeassistant.components.xiaomi_miio.config_flow.MiCloud.get_devices",
        side_effect=Exception({}),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                const.CONF_CLOUD_USERNAME: TEST_CLOUD_USER,
                const.CONF_CLOUD_PASSWORD: TEST_CLOUD_PASS,
                const.CONF_CLOUD_COUNTRY: TEST_CLOUD_COUNTRY,
            },
        )

    assert result["type"] == "abort"
    assert result["reason"] == "unknown"


async def test_config_flow_gateway_cloud_missing_token(hass: HomeAssistant) -> None:
    """Test a failed config flow using cloud with a missing token."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "cloud"
    assert result["errors"] == {}

    cloud_device = [
        {
            "parent_id": None,
            "name": TEST_NAME,
            "model": TEST_MODEL,
            "localip": TEST_HOST,
            "mac": TEST_MAC_DEVICE,
            "token": None,
        }
    ]

    with patch(
        "homeassistant.components.xiaomi_miio.config_flow.MiCloud.get_devices",
        return_value=cloud_device,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                const.CONF_CLOUD_USERNAME: TEST_CLOUD_USER,
                const.CONF_CLOUD_PASSWORD: TEST_CLOUD_PASS,
                const.CONF_CLOUD_COUNTRY: TEST_CLOUD_COUNTRY,
            },
        )

    assert result["type"] == "abort"
    assert result["reason"] == "incomplete_info"


async def test_zeroconf_gateway_success(hass: HomeAssistant) -> None:
    """Test a successful zeroconf discovery of a gateway."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address(TEST_HOST),
            ip_addresses=[ip_address(TEST_HOST)],
            hostname="mock_hostname",
            name=TEST_ZEROCONF_NAME,
            port=None,
            properties={ZEROCONF_MAC: TEST_MAC},
            type="mock_type",
        ),
    )

    assert result["type"] == "form"
    assert result["step_id"] == "cloud"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            const.CONF_CLOUD_USERNAME: TEST_CLOUD_USER,
            const.CONF_CLOUD_PASSWORD: TEST_CLOUD_PASS,
            const.CONF_CLOUD_COUNTRY: TEST_CLOUD_COUNTRY,
        },
    )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        const.CONF_FLOW_TYPE: const.CONF_GATEWAY,
        const.CONF_CLOUD_USERNAME: TEST_CLOUD_USER,
        const.CONF_CLOUD_PASSWORD: TEST_CLOUD_PASS,
        const.CONF_CLOUD_COUNTRY: TEST_CLOUD_COUNTRY,
        CONF_HOST: TEST_HOST,
        CONF_TOKEN: TEST_TOKEN,
        CONF_MODEL: TEST_MODEL,
        const.CONF_MAC: TEST_MAC,
    }


async def test_zeroconf_unknown_device(hass: HomeAssistant) -> None:
    """Test a failed zeroconf discovery because of a unknown device."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address(TEST_HOST),
            ip_addresses=[ip_address(TEST_HOST)],
            hostname="mock_hostname",
            name="not-a-xiaomi-miio-device",
            port=None,
            properties={ZEROCONF_MAC: TEST_MAC},
            type="mock_type",
        ),
    )

    assert result["type"] == "abort"
    assert result["reason"] == "not_xiaomi_miio"


async def test_zeroconf_no_data(hass: HomeAssistant) -> None:
    """Test a failed zeroconf discovery because of no data."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=None,
            ip_addresses=[],
            hostname="mock_hostname",
            name=None,
            port=None,
            properties={},
            type="mock_type",
        ),
    )

    assert result["type"] == "abort"
    assert result["reason"] == "not_xiaomi_miio"


async def test_zeroconf_missing_data(hass: HomeAssistant) -> None:
    """Test a failed zeroconf discovery because of missing data."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address(TEST_HOST),
            ip_addresses=[ip_address(TEST_HOST)],
            hostname="mock_hostname",
            name=TEST_ZEROCONF_NAME,
            port=None,
            properties={},
            type="mock_type",
        ),
    )

    assert result["type"] == "abort"
    assert result["reason"] == "not_xiaomi_miio"


async def test_config_flow_step_device_connect_error(hass: HomeAssistant) -> None:
    """Test config flow, device connection error."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "cloud"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_MANUAL: True},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "manual"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.xiaomi_miio.device.Device.info",
        side_effect=DeviceException({}),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: TEST_HOST, CONF_TOKEN: TEST_TOKEN},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "connect"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_config_flow_step_unknown_device(hass: HomeAssistant) -> None:
    """Test config flow, unknown device error."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "cloud"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_MANUAL: True},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "manual"
    assert result["errors"] == {}

    mock_info = get_mock_info(model="UNKNOWN")

    with patch(
        "homeassistant.components.xiaomi_miio.device.Device.info",
        return_value=mock_info,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: TEST_HOST, CONF_TOKEN: TEST_TOKEN},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "connect"
    assert result["errors"] == {"base": "unknown_device"}


async def test_config_flow_step_device_manual_model_error(hass: HomeAssistant) -> None:
    """Test config flow, device connection error, model None."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "cloud"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_MANUAL: True},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "manual"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.xiaomi_miio.device.Device.info",
        return_value=get_mock_info(model=None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: TEST_HOST, CONF_TOKEN: TEST_TOKEN},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "connect"
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.xiaomi_miio.device.Device.info",
        side_effect=Exception({}),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_MODEL: TEST_MODEL},
        )

    assert result["type"] == "abort"
    assert result["reason"] == "unknown"


async def test_config_flow_step_device_manual_model_succes(hass: HomeAssistant) -> None:
    """Test config flow, device connection error, manual model."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "cloud"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_MANUAL: True},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "manual"
    assert result["errors"] == {}

    error = DeviceException({})
    error.__cause__ = ChecksumError({})
    with patch(
        "homeassistant.components.xiaomi_miio.device.Device.info",
        side_effect=error,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: TEST_HOST, CONF_TOKEN: TEST_TOKEN},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "connect"
    assert result["errors"] == {"base": "wrong_token"}

    overwrite_model = const.MODELS_VACUUM[0]

    with patch(
        "homeassistant.components.xiaomi_miio.device.Device.info",
        side_effect=DeviceException({}),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_MODEL: overwrite_model},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == overwrite_model
    assert result["data"] == {
        const.CONF_FLOW_TYPE: const.CONF_DEVICE,
        const.CONF_CLOUD_USERNAME: None,
        const.CONF_CLOUD_PASSWORD: None,
        const.CONF_CLOUD_COUNTRY: None,
        CONF_HOST: TEST_HOST,
        CONF_TOKEN: TEST_TOKEN,
        CONF_MODEL: overwrite_model,
        const.CONF_MAC: None,
    }


async def config_flow_device_success(hass, model_to_test):
    """Test a successful config flow for a device (base class)."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "cloud"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_MANUAL: True},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "manual"
    assert result["errors"] == {}

    mock_info = get_mock_info(model=model_to_test)

    with patch(
        "homeassistant.components.xiaomi_miio.device.Device.info",
        return_value=mock_info,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: TEST_HOST, CONF_TOKEN: TEST_TOKEN},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == model_to_test
    assert result["data"] == {
        const.CONF_FLOW_TYPE: const.CONF_DEVICE,
        const.CONF_CLOUD_USERNAME: None,
        const.CONF_CLOUD_PASSWORD: None,
        const.CONF_CLOUD_COUNTRY: None,
        CONF_HOST: TEST_HOST,
        CONF_TOKEN: TEST_TOKEN,
        CONF_MODEL: model_to_test,
        const.CONF_MAC: TEST_MAC,
    }


async def config_flow_generic_roborock(hass):
    """Test a successful config flow for a generic roborock vacuum."""
    dummy_model = "roborock.vacuum.dummy"

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "cloud"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_MANUAL: True},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "manual"
    assert result["errors"] == {}

    mock_info = get_mock_info(model=dummy_model)

    with patch(
        "homeassistant.components.xiaomi_miio.device.Device.info",
        return_value=mock_info,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: TEST_HOST, CONF_TOKEN: TEST_TOKEN},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == dummy_model
    assert result["data"] == {
        const.CONF_FLOW_TYPE: const.CONF_DEVICE,
        const.CONF_CLOUD_USERNAME: None,
        const.CONF_CLOUD_PASSWORD: None,
        const.CONF_CLOUD_COUNTRY: None,
        CONF_HOST: TEST_HOST,
        CONF_TOKEN: TEST_TOKEN,
        CONF_MODEL: dummy_model,
        const.CONF_MAC: TEST_MAC,
    }


async def zeroconf_device_success(hass, zeroconf_name_to_test, model_to_test):
    """Test a successful zeroconf discovery of a device  (base class)."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address(TEST_HOST),
            ip_addresses=[ip_address(TEST_HOST)],
            hostname="mock_hostname",
            name=zeroconf_name_to_test,
            port=None,
            properties={"poch": f"0:mac={TEST_MAC_DEVICE}\x00"},
            type="mock_type",
        ),
    )

    assert result["type"] == "form"
    assert result["step_id"] == "cloud"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_MANUAL: True},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "manual"
    assert result["errors"] == {}

    mock_info = get_mock_info(model=model_to_test)

    with patch(
        "homeassistant.components.xiaomi_miio.device.Device.info",
        return_value=mock_info,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: TEST_TOKEN},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == model_to_test
    assert result["data"] == {
        const.CONF_FLOW_TYPE: const.CONF_DEVICE,
        const.CONF_CLOUD_USERNAME: None,
        const.CONF_CLOUD_PASSWORD: None,
        const.CONF_CLOUD_COUNTRY: None,
        CONF_HOST: TEST_HOST,
        CONF_TOKEN: TEST_TOKEN,
        CONF_MODEL: model_to_test,
        const.CONF_MAC: TEST_MAC,
    }


async def test_config_flow_plug_success(hass: HomeAssistant) -> None:
    """Test a successful config flow for a plug."""
    test_plug_model = const.MODELS_SWITCH[0]
    await config_flow_device_success(hass, test_plug_model)


async def test_zeroconf_plug_success(hass: HomeAssistant) -> None:
    """Test a successful zeroconf discovery of a plug."""
    test_plug_model = const.MODELS_SWITCH[0]
    test_zeroconf_name = const.MODELS_SWITCH[0].replace(".", "-")
    await zeroconf_device_success(hass, test_zeroconf_name, test_plug_model)


async def test_config_flow_vacuum_success(hass: HomeAssistant) -> None:
    """Test a successful config flow for a vacuum."""
    test_vacuum_model = const.MODELS_VACUUM[0]
    await config_flow_device_success(hass, test_vacuum_model)


async def test_zeroconf_vacuum_success(hass: HomeAssistant) -> None:
    """Test a successful zeroconf discovery of a vacuum."""
    test_vacuum_model = const.MODELS_VACUUM[0]
    test_zeroconf_name = const.MODELS_VACUUM[0].replace(".", "-")
    await zeroconf_device_success(hass, test_zeroconf_name, test_vacuum_model)


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test specifying non default settings using options flow."""
    config_entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        data={
            const.CONF_CLOUD_USERNAME: TEST_CLOUD_USER,
            const.CONF_CLOUD_PASSWORD: TEST_CLOUD_PASS,
            const.CONF_CLOUD_COUNTRY: TEST_CLOUD_COUNTRY,
            const.CONF_FLOW_TYPE: const.CONF_GATEWAY,
            CONF_HOST: TEST_HOST,
            CONF_TOKEN: TEST_TOKEN,
            CONF_MODEL: TEST_MODEL,
            const.CONF_MAC: TEST_MAC,
        },
        title=TEST_NAME,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            const.CONF_CLOUD_SUBDEVICES: True,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        const.CONF_CLOUD_SUBDEVICES: True,
    }


async def test_options_flow_incomplete(hass: HomeAssistant) -> None:
    """Test specifying incomplete settings using options flow."""
    config_entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        data={
            const.CONF_CLOUD_USERNAME: None,
            const.CONF_CLOUD_PASSWORD: None,
            const.CONF_CLOUD_COUNTRY: None,
            const.CONF_FLOW_TYPE: const.CONF_GATEWAY,
            CONF_HOST: TEST_HOST,
            CONF_TOKEN: TEST_TOKEN,
            CONF_MODEL: TEST_MODEL,
            const.CONF_MAC: TEST_MAC,
        },
        title=TEST_NAME,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            const.CONF_CLOUD_SUBDEVICES: True,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {"base": "cloud_credentials_incomplete"}


async def test_reauth(hass: HomeAssistant) -> None:
    """Test a reauth flow."""
    config_entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        data={
            const.CONF_CLOUD_USERNAME: None,
            const.CONF_CLOUD_PASSWORD: None,
            const.CONF_CLOUD_COUNTRY: None,
            const.CONF_FLOW_TYPE: const.CONF_GATEWAY,
            CONF_HOST: TEST_HOST,
            CONF_TOKEN: TEST_TOKEN,
            CONF_MODEL: TEST_MODEL,
            const.CONF_MAC: TEST_MAC,
        },
        title=TEST_NAME,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH},
        data=config_entry.data,
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "cloud"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            const.CONF_CLOUD_USERNAME: TEST_CLOUD_USER,
            const.CONF_CLOUD_PASSWORD: TEST_CLOUD_PASS,
            const.CONF_CLOUD_COUNTRY: TEST_CLOUD_COUNTRY,
        },
    )

    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"

    config_data = config_entry.data.copy()
    assert config_data == {
        const.CONF_FLOW_TYPE: const.CONF_GATEWAY,
        const.CONF_CLOUD_USERNAME: TEST_CLOUD_USER,
        const.CONF_CLOUD_PASSWORD: TEST_CLOUD_PASS,
        const.CONF_CLOUD_COUNTRY: TEST_CLOUD_COUNTRY,
        CONF_HOST: TEST_HOST,
        CONF_TOKEN: TEST_TOKEN,
        CONF_MODEL: TEST_MODEL,
        const.CONF_MAC: TEST_MAC,
    }
