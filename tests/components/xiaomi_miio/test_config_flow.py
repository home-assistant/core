"""Test the Xiaomi Miio config flow."""
from unittest.mock import Mock, patch

from miio import DeviceException

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.xiaomi_miio import const
from homeassistant.components.xiaomi_miio.config_flow import (
    DEFAULT_DEVICE_NAME,
    DEFAULT_GATEWAY_NAME,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN

ZEROCONF_NAME = "name"
ZEROCONF_PROP = "properties"
ZEROCONF_MAC = "mac"

TEST_HOST = "1.2.3.4"
TEST_TOKEN = "12345678901234567890123456789012"
TEST_NAME = "Test_Gateway"
TEST_MODEL = const.MODELS_GATEWAY[0]
TEST_MAC = "ab:cd:ef:gh:ij:kl"
TEST_GATEWAY_ID = TEST_MAC
TEST_HARDWARE_VERSION = "AB123"
TEST_FIRMWARE_VERSION = "1.2.3_456"
TEST_ZEROCONF_NAME = "lumi-gateway-v3_miio12345678._miio._udp.local."
TEST_SUB_DEVICE_LIST = []


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


async def test_config_flow_step_gateway_connect_error(hass):
    """Test config flow, gateway connection error."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "device"
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
    assert result["step_id"] == "device"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_config_flow_gateway_success(hass):
    """Test a successful config flow."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "device"
    assert result["errors"] == {}

    mock_info = get_mock_info()

    with patch(
        "homeassistant.components.xiaomi_miio.device.Device.info",
        return_value=mock_info,
    ), patch(
        "homeassistant.components.xiaomi_miio.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: TEST_HOST, CONF_TOKEN: TEST_TOKEN},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == DEFAULT_GATEWAY_NAME
    assert result["data"] == {
        const.CONF_FLOW_TYPE: const.CONF_GATEWAY,
        CONF_HOST: TEST_HOST,
        CONF_TOKEN: TEST_TOKEN,
        const.CONF_MODEL: TEST_MODEL,
        const.CONF_MAC: TEST_MAC,
    }


async def test_zeroconf_gateway_success(hass):
    """Test a successful zeroconf discovery of a gateway."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data={
            zeroconf.ATTR_HOST: TEST_HOST,
            ZEROCONF_NAME: TEST_ZEROCONF_NAME,
            ZEROCONF_PROP: {ZEROCONF_MAC: TEST_MAC},
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "device"
    assert result["errors"] == {}

    mock_info = get_mock_info()

    with patch(
        "homeassistant.components.xiaomi_miio.device.Device.info",
        return_value=mock_info,
    ), patch(
        "homeassistant.components.xiaomi_miio.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: TEST_TOKEN},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == DEFAULT_GATEWAY_NAME
    assert result["data"] == {
        const.CONF_FLOW_TYPE: const.CONF_GATEWAY,
        CONF_HOST: TEST_HOST,
        CONF_TOKEN: TEST_TOKEN,
        const.CONF_MODEL: TEST_MODEL,
        const.CONF_MAC: TEST_MAC,
    }


async def test_zeroconf_unknown_device(hass):
    """Test a failed zeroconf discovery because of a unknown device."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data={
            zeroconf.ATTR_HOST: TEST_HOST,
            ZEROCONF_NAME: "not-a-xiaomi-miio-device",
            ZEROCONF_PROP: {ZEROCONF_MAC: TEST_MAC},
        },
    )

    assert result["type"] == "abort"
    assert result["reason"] == "not_xiaomi_miio"


async def test_zeroconf_no_data(hass):
    """Test a failed zeroconf discovery because of no data."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data={}
    )

    assert result["type"] == "abort"
    assert result["reason"] == "not_xiaomi_miio"


async def test_zeroconf_missing_data(hass):
    """Test a failed zeroconf discovery because of missing data."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data={zeroconf.ATTR_HOST: TEST_HOST, ZEROCONF_NAME: TEST_ZEROCONF_NAME},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "not_xiaomi_miio"


async def test_config_flow_step_device_connect_error(hass):
    """Test config flow, device connection error."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "device"
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
    assert result["step_id"] == "device"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_config_flow_step_unknown_device(hass):
    """Test config flow, unknown device error."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "device"
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
    assert result["step_id"] == "device"
    assert result["errors"] == {"base": "unknown_device"}


async def test_import_flow_success(hass):
    """Test a successful import form yaml for a device."""
    mock_info = get_mock_info(model=const.MODELS_SWITCH[0])

    with patch(
        "homeassistant.components.xiaomi_miio.device.Device.info",
        return_value=mock_info,
    ), patch(
        "homeassistant.components.xiaomi_miio.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_NAME: TEST_NAME, CONF_HOST: TEST_HOST, CONF_TOKEN: TEST_TOKEN},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        const.CONF_FLOW_TYPE: const.CONF_DEVICE,
        CONF_HOST: TEST_HOST,
        CONF_TOKEN: TEST_TOKEN,
        const.CONF_MODEL: const.MODELS_SWITCH[0],
        const.CONF_MAC: TEST_MAC,
    }


async def test_config_flow_step_device_manual_model_succes(hass):
    """Test config flow, device connection error, manual model."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "device"
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
    assert result["step_id"] == "device"
    assert result["errors"] == {"base": "cannot_connect"}

    overwrite_model = const.MODELS_VACUUM[0]

    with patch(
        "homeassistant.components.xiaomi_miio.device.Device.info",
        side_effect=DeviceException({}),
    ), patch(
        "homeassistant.components.xiaomi_miio.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: TEST_TOKEN, const.CONF_MODEL: overwrite_model},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == DEFAULT_DEVICE_NAME
    assert result["data"] == {
        const.CONF_FLOW_TYPE: const.CONF_DEVICE,
        CONF_HOST: TEST_HOST,
        CONF_TOKEN: TEST_TOKEN,
        const.CONF_MODEL: overwrite_model,
        const.CONF_MAC: None,
    }


async def config_flow_device_success(hass, model_to_test):
    """Test a successful config flow for a device (base class)."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "device"
    assert result["errors"] == {}

    mock_info = get_mock_info(model=model_to_test)

    with patch(
        "homeassistant.components.xiaomi_miio.device.Device.info",
        return_value=mock_info,
    ), patch(
        "homeassistant.components.xiaomi_miio.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: TEST_HOST, CONF_TOKEN: TEST_TOKEN},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == DEFAULT_DEVICE_NAME
    assert result["data"] == {
        const.CONF_FLOW_TYPE: const.CONF_DEVICE,
        CONF_HOST: TEST_HOST,
        CONF_TOKEN: TEST_TOKEN,
        const.CONF_MODEL: model_to_test,
        const.CONF_MAC: TEST_MAC,
    }


async def zeroconf_device_success(hass, zeroconf_name_to_test, model_to_test):
    """Test a successful zeroconf discovery of a device  (base class)."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data={
            zeroconf.ATTR_HOST: TEST_HOST,
            ZEROCONF_NAME: zeroconf_name_to_test,
            ZEROCONF_PROP: {ZEROCONF_MAC: TEST_MAC},
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "device"
    assert result["errors"] == {}

    mock_info = get_mock_info(model=model_to_test)

    with patch(
        "homeassistant.components.xiaomi_miio.device.Device.info",
        return_value=mock_info,
    ), patch(
        "homeassistant.components.xiaomi_miio.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: TEST_TOKEN},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == DEFAULT_DEVICE_NAME
    assert result["data"] == {
        const.CONF_FLOW_TYPE: const.CONF_DEVICE,
        CONF_HOST: TEST_HOST,
        CONF_TOKEN: TEST_TOKEN,
        const.CONF_MODEL: model_to_test,
        const.CONF_MAC: TEST_MAC,
    }


async def test_config_flow_plug_success(hass):
    """Test a successful config flow for a plug."""
    test_plug_model = const.MODELS_SWITCH[0]
    await config_flow_device_success(hass, test_plug_model)


async def test_zeroconf_plug_success(hass):
    """Test a successful zeroconf discovery of a plug."""
    test_plug_model = const.MODELS_SWITCH[0]
    test_zeroconf_name = const.MODELS_SWITCH[0].replace(".", "-")
    await zeroconf_device_success(hass, test_zeroconf_name, test_plug_model)


async def test_config_flow_vacuum_success(hass):
    """Test a successful config flow for a vacuum."""
    test_vacuum_model = const.MODELS_VACUUM[0]
    await config_flow_device_success(hass, test_vacuum_model)


async def test_zeroconf_vacuum_success(hass):
    """Test a successful zeroconf discovery of a vacuum."""
    test_vacuum_model = const.MODELS_VACUUM[0]
    test_zeroconf_name = const.MODELS_VACUUM[0].replace(".", "-")
    await zeroconf_device_success(hass, test_zeroconf_name, test_vacuum_model)
