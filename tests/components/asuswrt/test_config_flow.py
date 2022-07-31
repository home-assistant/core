"""Tests for the AsusWrt config flow."""
from socket import gaierror
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant import data_entry_flow
from homeassistant.components.asuswrt.const import (
    CONF_DNSMASQ,
    CONF_INTERFACE,
    CONF_REQUIRE_IP,
    CONF_SSH_KEY,
    CONF_TRACK_UNKNOWN,
    DOMAIN,
)
from homeassistant.components.device_tracker.const import CONF_CONSIDER_HOME
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)

from tests.common import MockConfigEntry

HOST = "myrouter.asuswrt.com"
IP_ADDRESS = "192.168.1.1"
MAC_ADDR = "a1:b1:c1:d1:e1:f1"
SSH_KEY = "1234"

CONFIG_DATA = {
    CONF_HOST: HOST,
    CONF_PORT: 22,
    CONF_PROTOCOL: "telnet",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pwd",
    CONF_MODE: "ap",
}

PATCH_GET_HOST = patch(
    "homeassistant.components.asuswrt.config_flow.socket.gethostbyname",
    return_value=IP_ADDRESS,
)

PATCH_SETUP_ENTRY = patch(
    "homeassistant.components.asuswrt.async_setup_entry",
    return_value=True,
)


@pytest.fixture(name="mock_unique_id")
def mock_unique_id_fixture():
    """Mock returned unique id."""
    return {}


@pytest.fixture(name="connect")
def mock_controller_connect(mock_unique_id):
    """Mock a successful connection."""
    with patch("homeassistant.components.asuswrt.router.AsusWrt") as service_mock:
        service_mock.return_value.connection.async_connect = AsyncMock()
        service_mock.return_value.is_connected = True
        service_mock.return_value.connection.disconnect = Mock()
        service_mock.return_value.async_get_nvram = AsyncMock(
            return_value=mock_unique_id
        )
        yield service_mock


@pytest.mark.usefixtures("connect")
@pytest.mark.parametrize(
    "unique_id",
    [{}, {"label_mac": MAC_ADDR}],
)
async def test_user(hass, mock_unique_id, unique_id):
    """Test user config."""
    mock_unique_id.update(unique_id)
    flow_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER, "show_advanced_options": True}
    )
    assert flow_result["type"] == data_entry_flow.FlowResultType.FORM
    assert flow_result["step_id"] == "user"

    # test with all provided
    with PATCH_GET_HOST, PATCH_SETUP_ENTRY as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            flow_result["flow_id"],
            user_input=CONFIG_DATA,
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == HOST
        assert result["data"] == CONFIG_DATA

        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ["config", "error"],
    [
        ({CONF_PASSWORD: None}, "pwd_or_ssh"),
        ({CONF_SSH_KEY: SSH_KEY}, "pwd_and_ssh"),
    ],
)
async def test_error_wrong_password_ssh(hass, config, error):
    """Test we abort for wrong password and ssh file combination."""
    config_data = CONFIG_DATA.copy()
    config_data.update(config)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER, "show_advanced_options": True},
        data=config_data,
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_error_invalid_ssh(hass):
    """Test we abort if invalid ssh file is provided."""
    config_data = CONFIG_DATA.copy()
    config_data.pop(CONF_PASSWORD)
    config_data[CONF_SSH_KEY] = SSH_KEY

    with patch(
        "homeassistant.components.asuswrt.config_flow.os.path.isfile",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER, "show_advanced_options": True},
            data=config_data,
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {"base": "ssh_not_file"}


async def test_error_invalid_host(hass):
    """Test we abort if host name is invalid."""
    with patch(
        "homeassistant.components.asuswrt.config_flow.socket.gethostbyname",
        side_effect=gaierror,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG_DATA,
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_host"}


async def test_abort_if_not_unique_id_setup(hass):
    """Test we abort if component without uniqueid is already setup."""
    MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=CONFIG_DATA,
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "no_unique_id"


@pytest.mark.usefixtures("connect")
async def test_update_uniqueid_exist(hass, mock_unique_id):
    """Test we update entry if uniqueid is already configured."""
    mock_unique_id.update({"label_mac": MAC_ADDR})
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={**CONFIG_DATA, CONF_HOST: "10.10.10.10"},
        unique_id=MAC_ADDR,
    )
    existing_entry.add_to_hass(hass)

    # test with all provided
    with PATCH_GET_HOST, PATCH_SETUP_ENTRY:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER, "show_advanced_options": True},
            data=CONFIG_DATA,
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == HOST
        assert result["data"] == CONFIG_DATA
        prev_entry = hass.config_entries.async_get_entry(existing_entry.entry_id)
        assert not prev_entry


@pytest.mark.usefixtures("connect")
async def test_abort_invalid_unique_id(hass):
    """Test we abort if uniqueid not available."""
    MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA,
        unique_id=MAC_ADDR,
    ).add_to_hass(hass)

    with PATCH_GET_HOST:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG_DATA,
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "invalid_unique_id"


@pytest.mark.parametrize(
    ["side_effect", "error"],
    [
        (OSError, "cannot_connect"),
        (TypeError, "unknown"),
        (None, "cannot_connect"),
    ],
)
async def test_on_connect_failed(hass, side_effect, error):
    """Test when we have errors connecting the router."""
    flow_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER, "show_advanced_options": True},
    )

    with PATCH_GET_HOST, patch(
        "homeassistant.components.asuswrt.router.AsusWrt"
    ) as asus_wrt:
        asus_wrt.return_value.connection.async_connect = AsyncMock(
            side_effect=side_effect
        )
        asus_wrt.return_value.is_connected = False

        result = await hass.config_entries.flow.async_configure(
            flow_result["flow_id"], user_input=CONFIG_DATA
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {"base": error}


async def test_options_flow(hass):
    """Test config flow options."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA,
        options={CONF_REQUIRE_IP: True},
    )
    config_entry.add_to_hass(hass)

    with PATCH_SETUP_ENTRY:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_CONSIDER_HOME: 20,
                CONF_TRACK_UNKNOWN: True,
                CONF_INTERFACE: "aaa",
                CONF_DNSMASQ: "bbb",
                CONF_REQUIRE_IP: False,
            },
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert config_entry.options[CONF_CONSIDER_HOME] == 20
        assert config_entry.options[CONF_TRACK_UNKNOWN] is True
        assert config_entry.options[CONF_INTERFACE] == "aaa"
        assert config_entry.options[CONF_DNSMASQ] == "bbb"
        assert config_entry.options[CONF_REQUIRE_IP] is False
