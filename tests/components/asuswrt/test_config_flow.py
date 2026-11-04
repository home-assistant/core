"""Tests for the AsusWrt config flow."""

from socket import gaierror
from typing import Any
from unittest.mock import MagicMock, patch

from asusrouter import AsusRouterError
from asusrouter.modules.identity import AsusDevice
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.asuswrt.const import (
    CONF_DNSMASQ,
    CONF_INTERFACE,
    CONF_MORE_OPTIONS,
    CONF_REQUIRE_IP,
    CONF_SSH_KEY,
    CONF_TRACK_UNKNOWN,
    DOMAIN,
    MODE_AP,
    MODE_ROUTER,
    PROTOCOL_HTTPS,
    PROTOCOL_SSH,
    PROTOCOL_TELNET,
)
from homeassistant.components.device_tracker import CONF_CONSIDER_HOME
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
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
from homeassistant.data_entry_flow import FlowResultType

from .common import ASUSWRT_BASE, HOST, ROUTER_MAC_ADDR

SSH_KEY = "1234"

CONFIG_DATA = {
    CONF_HOST: HOST,
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pwd",
}

CONFIG_SCHEMA_HTTP = {
    **CONFIG_DATA,
    CONF_PROTOCOL: PROTOCOL_HTTPS,
    CONF_MORE_OPTIONS: {CONF_PORT: 8443},
}

CONFIG_DATA_HTTP = {
    **CONFIG_DATA,
    CONF_PROTOCOL: PROTOCOL_HTTPS,
    CONF_PORT: 8443,
}

CONFIG_SCHEMA_TELNET = {
    **CONFIG_DATA,
    CONF_PROTOCOL: PROTOCOL_TELNET,
    CONF_MORE_OPTIONS: {CONF_PORT: 23},
}

CONFIG_DATA_TELNET = {
    **CONFIG_DATA,
    CONF_PROTOCOL: PROTOCOL_TELNET,
    CONF_PORT: 23,
}

CONFIG_SCHEMA_SSH = {
    **CONFIG_DATA,
    CONF_PROTOCOL: PROTOCOL_SSH,
    CONF_MORE_OPTIONS: {CONF_PORT: 22},
}


@pytest.fixture(name="patch_get_host", autouse=True)
def mock_controller_patch_get_host():
    """Mock call to socket gethostbyname function."""
    with patch(
        f"{ASUSWRT_BASE}.config_flow.socket.gethostbyname", return_value="192.168.1.1"
    ) as get_host_mock:
        yield get_host_mock


@pytest.fixture(name="patch_is_file", autouse=True)
def mock_controller_patch_is_file():
    """Mock the config flow _is_file helper."""
    with patch(
        f"{ASUSWRT_BASE}.config_flow._is_file", return_value=True
    ) as is_file_mock:
        yield is_file_mock


@pytest.mark.parametrize(
    ("unique_id", "expected_unique_id"),
    [({}, None), ({"label_mac": ROUTER_MAC_ADDR}, ROUTER_MAC_ADDR)],
)
async def test_user_legacy(
    hass: HomeAssistant,
    connect_legacy,
    patch_setup_entry,
    unique_id,
    expected_unique_id: str | None,
) -> None:
    """Test user config."""
    flow_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert flow_result["type"] is FlowResultType.FORM
    assert flow_result["step_id"] == "user"

    connect_legacy.return_value.async_get_nvram.return_value = unique_id

    # test with all provided
    legacy_result = await hass.config_entries.flow.async_configure(
        flow_result["flow_id"], user_input=CONFIG_SCHEMA_TELNET
    )
    await hass.async_block_till_done()

    assert legacy_result["type"] is FlowResultType.FORM
    assert legacy_result["step_id"] == "legacy"

    # complete configuration
    result = await hass.config_entries.flow.async_configure(
        legacy_result["flow_id"], user_input={CONF_MODE: MODE_AP}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"] == {**CONFIG_DATA_TELNET, CONF_MODE: MODE_AP}
    assert result["result"].unique_id == expected_unique_id

    assert len(patch_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("unique_id", [None, ROUTER_MAC_ADDR])
async def test_user_http(
    hass: HomeAssistant, connect_http, patch_setup_entry, unique_id
) -> None:
    """Test user config http."""
    flow_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert flow_result["type"] is FlowResultType.FORM
    assert flow_result["step_id"] == "user"

    connect_http.return_value.async_get_identity.return_value = AsusDevice(
        mac=unique_id,
        model="FAKE_MODEL",
        firmware="FAKE_FIRMWARE",
    )

    # test with all provided
    result = await hass.config_entries.flow.async_configure(
        flow_result["flow_id"], user_input=CONFIG_SCHEMA_HTTP
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"] == CONFIG_DATA_HTTP
    assert result["result"].unique_id == unique_id

    assert len(patch_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("config", [CONFIG_SCHEMA_TELNET, CONFIG_SCHEMA_HTTP])
@pytest.mark.usefixtures("connect_http", "patch_setup_entry")
async def test_error_pwd_required(hass: HomeAssistant, config) -> None:
    """Test we abort for missing password."""
    config_data = {k: v for k, v in config.items() if k != CONF_PASSWORD}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=config_data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_BASE: "pwd_required"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_SCHEMA_HTTP,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("connect_legacy", "patch_setup_entry")
async def test_error_no_password_ssh(hass: HomeAssistant) -> None:
    """Test we abort for wrong password and ssh file combination."""
    config_data = {k: v for k, v in CONFIG_SCHEMA_SSH.items() if k != CONF_PASSWORD}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=config_data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_BASE: "pwd_or_ssh"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_SCHEMA_SSH,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "legacy"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MODE: MODE_AP}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("connect_legacy", "patch_setup_entry")
async def test_error_password_and_ssh(hass: HomeAssistant) -> None:
    """Test we abort for both password and ssh file combination."""
    config_data = {**CONFIG_SCHEMA_SSH, CONF_MORE_OPTIONS: {CONF_SSH_KEY: SSH_KEY}}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=config_data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_BASE: "pwd_and_ssh"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_SCHEMA_SSH,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "legacy"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MODE: MODE_AP}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("connect_legacy", "patch_setup_entry")
async def test_error_invalid_ssh(hass: HomeAssistant, patch_is_file) -> None:
    """Test we abort if invalid ssh file is provided."""
    config_data = {k: v for k, v in CONFIG_SCHEMA_SSH.items() if k != CONF_PASSWORD}
    config_data[CONF_MORE_OPTIONS] = {CONF_SSH_KEY: SSH_KEY}

    def mock_is_file(file) -> bool:
        if str(file).endswith(SSH_KEY):
            return False
        return True

    patch_is_file.side_effect = mock_is_file
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=config_data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_BASE: "ssh_not_file"}

    patch_is_file.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=config_data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "legacy"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MODE: MODE_AP}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("connect_legacy", "patch_setup_entry")
async def test_error_invalid_host(hass: HomeAssistant, patch_get_host) -> None:
    """Test we abort if host name is invalid."""
    patch_get_host.side_effect = gaierror
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_SCHEMA_TELNET,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_BASE: "invalid_host"}

    patch_get_host.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_SCHEMA_TELNET,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "legacy"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MODE: MODE_AP}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_abort_if_not_unique_id_setup(hass: HomeAssistant) -> None:
    """Test we abort if component without uniqueid is already setup."""
    MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA_TELNET,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_unique_id"


async def test_update_uniqueid_exist(
    hass: HomeAssistant, connect_http, patch_setup_entry
) -> None:
    """Test we update entry if uniqueid is already configured."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={**CONFIG_DATA_HTTP, CONF_HOST: "10.10.10.10"},
        unique_id=ROUTER_MAC_ADDR,
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_SCHEMA_HTTP,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"] == CONFIG_DATA_HTTP
    assert result["result"].unique_id == ROUTER_MAC_ADDR
    prev_entry = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert not prev_entry


async def test_abort_invalid_unique_id(hass: HomeAssistant, connect_legacy) -> None:
    """Test we abort if uniqueid not available."""
    MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA_TELNET,
        unique_id=ROUTER_MAC_ADDR,
    ).add_to_hass(hass)

    connect_legacy.return_value.async_get_nvram.return_value = {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_SCHEMA_TELNET,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_unique_id"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (OSError, "cannot_connect"),
        (TypeError, "unknown"),
        (None, "cannot_connect"),
    ],
)
@pytest.mark.usefixtures("patch_setup_entry")
async def test_on_connect_legacy_failed(
    hass: HomeAssistant, connect_legacy, side_effect, error
) -> None:
    """Test when we have errors connecting the router with legacy library."""
    flow_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    connect_legacy.return_value.is_connected = False
    connect_legacy.return_value.connection.async_connect.side_effect = side_effect

    # go to legacy form
    result = await hass.config_entries.flow.async_configure(
        flow_result["flow_id"], user_input=CONFIG_SCHEMA_TELNET
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_BASE: error}

    connect_legacy.return_value.is_connected = True
    connect_legacy.return_value.connection.async_connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG_SCHEMA_TELNET
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "legacy"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MODE: MODE_AP}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (AsusRouterError, "cannot_connect"),
        (TypeError, "unknown"),
        (None, "cannot_connect"),
    ],
)
@pytest.mark.usefixtures("patch_setup_entry")
async def test_on_connect_http_failed(
    hass: HomeAssistant, connect_http, side_effect, error
) -> None:
    """Test when we have errors connecting the router with http library."""
    flow_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    connect_http.return_value.connected = False
    connect_http.return_value.async_connect.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        flow_result["flow_id"], user_input=CONFIG_SCHEMA_HTTP
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_BASE: error}

    connect_http.return_value.connected = True
    connect_http.return_value.async_connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG_SCHEMA_HTTP
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow_ap(hass: HomeAssistant, patch_setup_entry) -> None:
    """Test config flow options for ap mode."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={**CONFIG_DATA_TELNET, CONF_MODE: MODE_AP},
        options={CONF_REQUIRE_IP: True},
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
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

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        CONF_CONSIDER_HOME: 20,
        CONF_TRACK_UNKNOWN: True,
        CONF_INTERFACE: "aaa",
        CONF_DNSMASQ: "bbb",
        CONF_REQUIRE_IP: False,
    }


async def test_options_flow_router(hass: HomeAssistant, patch_setup_entry) -> None:
    """Test config flow options for router mode."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={**CONFIG_DATA_TELNET, CONF_MODE: MODE_ROUTER},
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
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

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        CONF_CONSIDER_HOME: 20,
        CONF_TRACK_UNKNOWN: True,
        CONF_INTERFACE: "aaa",
        CONF_DNSMASQ: "bbb",
    }


async def test_options_flow_http(hass: HomeAssistant, patch_setup_entry) -> None:
    """Test config flow options for http mode."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={**CONFIG_DATA_HTTP, CONF_MODE: MODE_ROUTER},
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
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

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        CONF_CONSIDER_HOME: 20,
        CONF_TRACK_UNKNOWN: True,
    }


@pytest.mark.usefixtures("connect_http_sens_detect")
async def test_reconfigure(hass: HomeAssistant, connect_http: MagicMock) -> None:
    """Test reconfiguring the router connection reloads the entry once."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=CONFIG_DATA_HTTP, unique_id=ROUTER_MAC_ADDR
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    connect_http.reset_mock()

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.2",
            CONF_USERNAME: "new_user",
            CONF_PASSWORD: "new_pwd",
            CONF_MORE_OPTIONS: {CONF_PORT: 443},
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_HOST: "192.168.1.2",
        CONF_USERNAME: "new_user",
        CONF_PASSWORD: "new_pwd",
        CONF_PROTOCOL: PROTOCOL_HTTPS,
        CONF_PORT: 443,
    }
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    # One connection to validate the input and one by the reloaded entry
    assert connect_http.return_value.async_connect.await_count == 2


@pytest.mark.usefixtures("connect_legacy", "patch_setup_entry")
async def test_reconfigure_password_to_ssh_key(hass: HomeAssistant) -> None:
    """Test reconfiguring a legacy router from a password to an SSH key."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**CONFIG_DATA, CONF_PROTOCOL: PROTOCOL_SSH, CONF_MODE: MODE_AP},
        unique_id=ROUTER_MAC_ADDR,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: HOST,
            CONF_USERNAME: "user",
            CONF_MORE_OPTIONS: {CONF_SSH_KEY: SSH_KEY},
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_HOST: HOST,
        CONF_USERNAME: "user",
        CONF_SSH_KEY: SSH_KEY,
        CONF_PROTOCOL: PROTOCOL_SSH,
        CONF_MODE: MODE_AP,
    }


@pytest.mark.parametrize(
    ("user_input", "error"),
    [
        pytest.param(
            {CONF_HOST: HOST, CONF_USERNAME: "user", CONF_MORE_OPTIONS: {}},
            "pwd_required",
            id="pwd_required",
        ),
        pytest.param(
            {
                **CONFIG_DATA,
                CONF_MORE_OPTIONS: {CONF_SSH_KEY: SSH_KEY},
            },
            "pwd_and_ssh",
            id="pwd_and_ssh",
        ),
    ],
)
@pytest.mark.usefixtures("connect_http", "patch_setup_entry")
async def test_reconfigure_invalid_input(
    hass: HomeAssistant, user_input: dict[str, Any], error: str
) -> None:
    """Test reconfigure shows input errors and can recover."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=CONFIG_DATA_HTTP, unique_id=ROUTER_MAC_ADDR
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {CONF_BASE: error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**CONFIG_DATA, CONF_MORE_OPTIONS: {CONF_PORT: 8443}},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == CONFIG_DATA_HTTP


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(AsusRouterError, "cannot_connect", id="cannot_connect"),
        pytest.param(TypeError, "unknown", id="unknown"),
        pytest.param(None, "cannot_connect", id="not_connected"),
    ],
)
@pytest.mark.usefixtures("patch_setup_entry")
async def test_reconfigure_connection_errors(
    hass: HomeAssistant,
    connect_http: MagicMock,
    side_effect: type[Exception] | None,
    error: str,
) -> None:
    """Test reconfigure shows connection errors and can recover."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=CONFIG_DATA_HTTP, unique_id=ROUTER_MAC_ADDR
    )
    entry.add_to_hass(hass)
    connect_http.return_value.connected = False
    connect_http.return_value.async_connect.side_effect = side_effect

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**CONFIG_DATA, CONF_MORE_OPTIONS: {CONF_PORT: 8443}},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {CONF_BASE: error}

    connect_http.return_value.connected = True
    connect_http.return_value.async_connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**CONFIG_DATA, CONF_MORE_OPTIONS: {CONF_PORT: 8443}},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("connect_http", "patch_setup_entry")
async def test_reconfigure_unique_id_mismatch(hass: HomeAssistant) -> None:
    """Test reconfiguring to a different router aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=CONFIG_DATA_HTTP, unique_id="11:22:33:44:55:66"
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**CONFIG_DATA, CONF_MORE_OPTIONS: {}, CONF_HOST: "192.168.1.2"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert entry.data == CONFIG_DATA_HTTP
