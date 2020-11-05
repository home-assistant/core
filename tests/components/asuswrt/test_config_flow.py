"""Tests for the AsusWrt config flow."""
import pytest

from aioasuswrt.asuswrt import Device

from homeassistant import data_entry_flow
from homeassistant.components import sensor
from homeassistant.components.asuswrt.const import (
    CONF_DNSMASQ,
    CONF_INTERFACE,
    CONF_REQUIRE_IP,
    CONF_SSH_KEY,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_MODE,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)

from tests.async_mock import AsyncMock, patch
from tests.common import MockConfigEntry

HOST = "myrouter.asuswrt.com"
SSH_KEY = "1234"

CONFIG_DATA = {
    CONF_HOST: HOST,
    CONF_PORT: 22,
    CONF_PROTOCOL: "ssh",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pwd",
    CONF_MODE: "router",
    CONF_REQUIRE_IP: True,
    CONF_INTERFACE: "eth0",
    CONF_DNSMASQ: "/var/lib/misc",
}

MOCK_DEVICES = {
    "a1:b1:c1:d1:e1:f1": Device("a1:b1:c1:d1:e1:f1", "192.168.1.2", "Test"),
    "a2:b2:c2:d2:e2:f2": Device("a2:b2:c2:d2:e2:f2", "192.168.1.3", "TestTwo"),
    "a3:b3:c3:d3:e3:f3": Device("a3:b3:c3:d3:e3:f3", "192.168.1.4", "TestThree"),
}
MOCK_BYTES_TOTAL = [60000000000, 50000000000]
MOCK_CURRENT_TRANSFER_RATES = [20000000, 10000000]


@pytest.fixture(name="connect")
def mock_controller_connect():
    """Mock a successful connection."""
    with patch("homeassistant.components.asuswrt.router.AsusWrt") as service_mock:
        service_mock.return_value.connection.async_connect = AsyncMock()
        service_mock.return_value.is_connected = True
        service_mock.return_value.connection.disconnect = AsyncMock()
        service_mock.return_value.async_get_nvram = AsyncMock(
            return_value={
                "model": "abcd",
                "firmver": "efg",
                "buildno": "123",
            }
        )
        service_mock.return_value.async_get_connected_devices = AsyncMock(
            return_value=MOCK_DEVICES
        )
        service_mock.return_value.async_get_bytes_total = AsyncMock(
            return_value=MOCK_BYTES_TOTAL
        )
        service_mock.return_value.async_get_current_transfer_rates = AsyncMock(
            return_value=MOCK_CURRENT_TRANSFER_RATES
        )
        yield service_mock


async def test_user(hass, connect):
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # test with all provided
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=CONFIG_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == HOST
    assert result["title"] == HOST
    assert result["data"] == CONFIG_DATA
    assert hass.states.get(f"{sensor.DOMAIN}.asuswrt_connected_devices").state == "3"
    assert hass.states.get(f"{sensor.DOMAIN}.asuswrt_download_speed").state == "160.0"
    assert hass.states.get(f"{sensor.DOMAIN}.asuswrt_download").state == "60.0"
    assert hass.states.get(f"{sensor.DOMAIN}.asuswrt_upload_speed").state == "80.0"
    assert hass.states.get(f"{sensor.DOMAIN}.asuswrt_upload").state == "50.0"


async def test_import(hass, connect):
    """Test import step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=CONFIG_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == HOST
    assert result["title"] == HOST
    assert result["data"] == CONFIG_DATA


async def test_error_no_password_ssh(hass):
    """Test we abort if component is already setup."""
    config_data = CONFIG_DATA.copy()
    config_data.pop(CONF_PASSWORD)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=config_data,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "pwd_or_ssh"}


async def test_error_both_password_ssh(hass):
    """Test we abort if component is already setup."""
    config_data = CONFIG_DATA.copy()
    config_data[CONF_SSH_KEY] = SSH_KEY
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=config_data,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "pwd_and_ssh"}


async def test_error_invalid_ssh(hass):
    """Test we abort if component is already setup."""
    config_data = CONFIG_DATA.copy()
    config_data.pop(CONF_PASSWORD)
    config_data[CONF_SSH_KEY] = SSH_KEY
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=config_data,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "ssh_not_file"}


async def test_abort_if_already_setup(hass):
    """Test we abort if component is already setup."""
    MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA,
        unique_id=HOST,
    ).add_to_hass(hass)

    # Should fail, same HOST (import)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=CONFIG_DATA,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    # Should fail, same HOST (flow)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=CONFIG_DATA,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_on_connect_failed(hass):
    """Test when we have errors during linking the router."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=CONFIG_DATA,
    )

    with patch("homeassistant.components.asuswrt.router.AsusWrt") as AsusWrt:
        AsusWrt.return_value.connection.async_connect = AsyncMock()
        AsusWrt.return_value.is_connected = False
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONFIG_DATA
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "cannot_connect"}

    with patch("homeassistant.components.asuswrt.router.AsusWrt") as AsusWrt:
        AsusWrt.return_value.connection.async_connect = AsyncMock(side_effect=OSError)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONFIG_DATA
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "cannot_connect"}

    with patch("homeassistant.components.asuswrt.router.AsusWrt") as AsusWrt:
        AsusWrt.return_value.connection.async_connect = AsyncMock(side_effect=TypeError)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONFIG_DATA
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "unknown"}
