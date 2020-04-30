"""Test the Xiaomi Miio config flow."""
from unittest.mock import Mock

from miio import DeviceException

from homeassistant import config_entries
from homeassistant.components.xiaomi_miio import config_flow, const
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN

from tests.async_mock import patch

TEST_HOST = "1.2.3.4"
TEST_TOKEN = "12345678901234567890123456789012"
TEST_NAME = "Test_Gateway"
TEST_MODEL = "model5"
TEST_MAC = "AB-CD-EF-GH-IJ-KL"
TEST_GATEWAY_ID = f"{TEST_MODEL}-{TEST_MAC}-gateway"
TEST_HARDWARE_VERSION = "AB123"
TEST_FIRMWARE_VERSION = "1.2.3_456"


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


async def test_config_flow_step_user_no_device(hass):
    """Test config flow, user step with no device selected."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {},)

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_device_selected"}


async def test_config_flow_step_gateway_connect_error(hass):
    """Test config flow, gateway connection error."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {config_flow.CONF_GATEWAY: True},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "gateway"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.xiaomi_miio.gateway.gateway.Gateway.info",
        side_effect=DeviceException({}),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: TEST_HOST, CONF_NAME: TEST_NAME, CONF_TOKEN: TEST_TOKEN},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "gateway"
    assert result["errors"] == {"base": "connect_error"}


async def test_config_flow_gateway_success(hass):
    """Test a successful config flow."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {config_flow.CONF_GATEWAY: True},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "gateway"
    assert result["errors"] == {}

    mock_info = get_mock_info()

    with patch(
        "homeassistant.components.xiaomi_miio.gateway.gateway.Gateway.info",
        return_value=mock_info,
    ), patch(
        "homeassistant.components.xiaomi_miio.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: TEST_HOST, CONF_NAME: TEST_NAME, CONF_TOKEN: TEST_TOKEN},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        config_flow.CONF_FLOW_TYPE: config_flow.CONF_GATEWAY,
        CONF_HOST: TEST_HOST,
        CONF_TOKEN: TEST_TOKEN,
        "gateway_id": TEST_GATEWAY_ID,
        "model": TEST_MODEL,
        "mac": TEST_MAC,
    }
