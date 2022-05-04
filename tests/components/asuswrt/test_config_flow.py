"""Tests for the AsusWrt config flow."""
from socket import gaierror
from unittest.mock import AsyncMock, Mock, patch

from pyasuswrt import AsusWrtError
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.asuswrt.const import (
    CONF_DNSMASQ,
    CONF_INTERFACE,
    CONF_REQUIRE_IP,
    CONF_SSH_KEY,
    CONF_TRACK_UNKNOWN,
    DOMAIN,
    MODE_AP,
    PROTOCOL_HTTP,
    PROTOCOL_HTTPS,
    PROTOCOL_SSH,
    PROTOCOL_TELNET,
)
from homeassistant.components.device_tracker import CONF_CONSIDER_HOME
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_BASE,
    CONF_HOST,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

KEY_HTTP = "http"
KEY_LEGACY = "legacy"

HOST = "myrouter.asuswrt.com"
IP_ADDRESS = "192.168.1.1"
MAC_ADDR = "a1:b1:c1:d1:e1:f1"
SSH_KEY = "1234"

CONFIG_DATA_HTTP = {
    CONF_HOST: HOST,
    CONF_PORT: 4567,
    CONF_PROTOCOL: PROTOCOL_HTTP,
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pwd",
}

CONFIG_DATA_HTTPS = {
    **CONFIG_DATA_HTTP,
    CONF_PROTOCOL: PROTOCOL_HTTPS,
}

CONFIG_DATA_SSH = {
    **CONFIG_DATA_HTTP,
    CONF_PROTOCOL: PROTOCOL_SSH,
}

CONFIG_DATA_TELNET = {
    **CONFIG_DATA_HTTP,
    CONF_PROTOCOL: PROTOCOL_TELNET,
}


PATCH_GET_HOST = patch(
    "homeassistant.components.asuswrt.config_flow.socket.gethostbyname",
    return_value=IP_ADDRESS,
)

PATCH_SETUP_ENTRY = patch(
    "homeassistant.components.asuswrt.async_setup_entry",
    return_value=True,
)


class ConnectionFake:
    """A fake of the `AsusWrtLegacy.connection` class."""

    def __init__(self, side_effect=None):
        """Initialize a fake `Connection` instance."""
        self.async_connect = AsyncMock(side_effect=side_effect)
        self.disconnect = Mock()


class AsusWrtLegacyFake:
    """A fake of the `AsusWrtLegacy` class."""

    def __init__(self, mac_addr=None, is_connected=True, side_effect=None):
        """Initialize a fake `AsusWrtLegacy` instance."""
        self._mac_addr = mac_addr
        self.is_connected = is_connected
        self.connection = ConnectionFake(side_effect)

    async def async_get_nvram(self, info_type):
        """Return nvram information."""
        return {"label_mac": self._mac_addr} if self._mac_addr else None


class AsusWrtHttpFake:
    """A fake of the `AsusWrtHttp` class."""

    def __init__(self, mac_addr=None, is_connected=True, side_effect=None):
        """Initialize a fake `AsusWrtLegacy` instance."""
        self.mac = mac_addr
        self.is_connected = is_connected
        self.async_connect = AsyncMock(side_effect=side_effect)
        self.async_disconnect = AsyncMock()
        self.async_get_settings = AsyncMock()


def patch_asuswrt(mac_addr=None, *, is_connected=True, side_effect=None):
    """Mock the `AsusWrtLegacy` and `AsusWrtHttp` classes."""
    return {
        KEY_LEGACY: patch(
            "homeassistant.components.asuswrt.bridge.AsusWrtLegacy",
            return_value=AsusWrtLegacyFake(mac_addr, is_connected, side_effect),
        ),
        KEY_HTTP: patch(
            "homeassistant.components.asuswrt.bridge.AsusWrtHttp",
            return_value=AsusWrtHttpFake(mac_addr, is_connected, side_effect),
        ),
    }


@pytest.mark.parametrize("unique_id", [None, MAC_ADDR])
async def test_user_legacy(hass, unique_id):
    """Test user config."""
    flow_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER, "show_advanced_options": True}
    )
    assert flow_result["type"] == data_entry_flow.FlowResultType.FORM
    assert flow_result["step_id"] == "user"

    # test with all provided
    with patch_asuswrt(unique_id)[
        KEY_LEGACY
    ], PATCH_GET_HOST, PATCH_SETUP_ENTRY as mock_setup_entry:

        # go to legacy form
        legacy_result = await hass.config_entries.flow.async_configure(
            flow_result["flow_id"], user_input=CONFIG_DATA_TELNET
        )
        await hass.async_block_till_done()

        assert legacy_result["type"] == data_entry_flow.FlowResultType.FORM
        assert legacy_result["step_id"] == "legacy"

        # complete configuration
        result = await hass.config_entries.flow.async_configure(
            legacy_result["flow_id"], user_input={CONF_MODE: MODE_AP}
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == HOST
        assert result["data"] == {**CONFIG_DATA_TELNET, CONF_MODE: MODE_AP}

        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("unique_id", [None, MAC_ADDR])
async def test_user_http(hass, unique_id):
    """Test user config http."""
    flow_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER, "show_advanced_options": True}
    )
    assert flow_result["type"] == data_entry_flow.FlowResultType.FORM
    assert flow_result["step_id"] == "user"

    # test with all provided
    with patch_asuswrt(unique_id)[
        KEY_HTTP
    ], PATCH_GET_HOST, PATCH_SETUP_ENTRY as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            flow_result["flow_id"], user_input=CONFIG_DATA_HTTP
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == HOST
        assert result["data"] == CONFIG_DATA_HTTP

        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "config", [CONFIG_DATA_TELNET, CONFIG_DATA_HTTP, CONFIG_DATA_HTTPS]
)
async def test_error_pwd_required(hass, config):
    """Test we abort for missing password."""
    config_data = {**config}
    config_data.pop(CONF_PASSWORD)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER, "show_advanced_options": True},
        data=config_data,
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {CONF_BASE: "pwd_required"}


async def test_error_invalid_ssh(hass):
    """Test we abort if invalid ssh file is provided."""
    config_data = {**CONFIG_DATA_SSH}
    config_data.pop(CONF_PASSWORD)

    with patch(
        "homeassistant.components.asuswrt.config_flow.os.path.isfile",
        return_value=False,
    ), PATCH_GET_HOST:

        # go to legacy form
        flow_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER, "show_advanced_options": True},
            data=config_data,
        )
        await hass.async_block_till_done()

        assert flow_result["type"] == data_entry_flow.FlowResultType.FORM
        assert flow_result["step_id"] == "legacy"

        # complete configuration
        result = await hass.config_entries.flow.async_configure(
            flow_result["flow_id"],
            user_input={CONF_SSH_KEY: "key", CONF_MODE: MODE_AP},
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "legacy"
        assert result["errors"] == {CONF_BASE: "ssh_not_file"}


async def test_error_invalid_host(hass):
    """Test we abort if host name is invalid."""
    with patch(
        "homeassistant.components.asuswrt.config_flow.socket.gethostbyname",
        side_effect=gaierror,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG_DATA_HTTP,
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {CONF_BASE: "invalid_host"}


async def test_abort_if_not_unique_id_setup(hass):
    """Test we abort if component without uniqueid is already setup."""
    MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA_HTTP,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=CONFIG_DATA_HTTP,
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "no_unique_id"


async def test_update_uniqueid_exist(hass):
    """Test we update entry if uniqueid is already configured."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={**CONFIG_DATA_HTTP, CONF_HOST: "10.10.10.10"},
        unique_id=MAC_ADDR,
    )
    existing_entry.add_to_hass(hass)

    with patch_asuswrt(MAC_ADDR)[KEY_HTTP], PATCH_GET_HOST, PATCH_SETUP_ENTRY:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER, "show_advanced_options": True},
            data=CONFIG_DATA_HTTP,
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == HOST
        assert result["data"] == CONFIG_DATA_HTTP
        prev_entry = hass.config_entries.async_get_entry(existing_entry.entry_id)
        assert not prev_entry


async def test_abort_invalid_unique_id(hass):
    """Test we abort if uniqueid not available."""
    MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA_HTTP,
        unique_id=MAC_ADDR,
    ).add_to_hass(hass)

    with patch_asuswrt()[KEY_HTTP], PATCH_GET_HOST:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG_DATA_HTTP,
        )
        await hass.async_block_till_done()

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
async def test_on_connect_legacy_failed(hass, side_effect, error):
    """Test when we have errors connecting the router with legacy library."""
    flow_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER, "show_advanced_options": True},
    )

    with patch_asuswrt(is_connected=False, side_effect=side_effect)[
        KEY_LEGACY
    ], PATCH_GET_HOST:
        # go to legacy form
        legacy_result = await hass.config_entries.flow.async_configure(
            flow_result["flow_id"], user_input=CONFIG_DATA_TELNET
        )
        await hass.async_block_till_done()

        assert legacy_result["type"] == data_entry_flow.FlowResultType.FORM
        assert legacy_result["step_id"] == "legacy"

        # complete configuration
        result = await hass.config_entries.flow.async_configure(
            legacy_result["flow_id"], user_input={CONF_MODE: MODE_AP}
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {CONF_BASE: error}


@pytest.mark.parametrize(
    ["side_effect", "error"],
    [
        (AsusWrtError, "cannot_connect"),
        (TypeError, "unknown"),
        (None, "cannot_connect"),
    ],
)
async def test_on_connect_http_failed(hass, side_effect, error):
    """Test when we have errors connecting the router with http library."""
    flow_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER, "show_advanced_options": True},
    )

    with patch_asuswrt(is_connected=False, side_effect=side_effect)[
        KEY_HTTP
    ], PATCH_GET_HOST:
        result = await hass.config_entries.flow.async_configure(
            flow_result["flow_id"], user_input=CONFIG_DATA_HTTP
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {CONF_BASE: error}


async def test_options_flow_ap(hass: HomeAssistant) -> None:
    """Test config flow options for ap mode."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={**CONFIG_DATA_TELNET, CONF_MODE: MODE_AP},
        options={CONF_REQUIRE_IP: True},
    )
    config_entry.add_to_hass(hass)

    with PATCH_SETUP_ENTRY:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"
        assert CONF_REQUIRE_IP in result["data_schema"].schema

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


async def test_options_flow_router(hass: HomeAssistant) -> None:
    """Test config flow options for router mode."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={**CONFIG_DATA_TELNET, CONF_MODE: "router"},
    )
    config_entry.add_to_hass(hass)

    with PATCH_SETUP_ENTRY:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"
        assert CONF_REQUIRE_IP not in result["data_schema"].schema

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_CONSIDER_HOME: 20,
                CONF_TRACK_UNKNOWN: True,
                CONF_INTERFACE: "aaa",
                CONF_DNSMASQ: "bbb",
            },
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert config_entry.options[CONF_CONSIDER_HOME] == 20
        assert config_entry.options[CONF_TRACK_UNKNOWN] is True
        assert config_entry.options[CONF_INTERFACE] == "aaa"
        assert config_entry.options[CONF_DNSMASQ] == "bbb"


async def test_options_flow_http(hass: HomeAssistant) -> None:
    """Test config flow options for http mode."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={**CONFIG_DATA_HTTP, CONF_MODE: "router"},
    )
    config_entry.add_to_hass(hass)

    with PATCH_SETUP_ENTRY:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"
        assert CONF_INTERFACE not in result["data_schema"].schema
        assert CONF_DNSMASQ not in result["data_schema"].schema
        assert CONF_REQUIRE_IP not in result["data_schema"].schema

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_CONSIDER_HOME: 20,
                CONF_TRACK_UNKNOWN: True,
            },
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert config_entry.options[CONF_CONSIDER_HOME] == 20
        assert config_entry.options[CONF_TRACK_UNKNOWN] is True
