"""Testing file for config flow ProxmoxVE."""
import proxmoxer
from requests.exceptions import ConnectTimeout, SSLError

from homeassistant.components.proxmoxve.const import (
    CONF_LXC,
    CONF_NODE,
    CONF_QEMU,
    CONF_REALM,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import patch

USER_INPUT_OK = {
    CONF_HOST: "192.168.10.11",
    CONF_PORT: 8006,
    CONF_USERNAME: "root",
    CONF_PASSWORD: "secret",
    CONF_REALM: "pam",
    CONF_VERIFY_SSL: True,
    CONF_NODE: "pve",
    CONF_QEMU: [100, 101, 102],
    CONF_LXC: [201, 202, 203],
}

USER_INPUT_REQONLY = {
    CONF_HOST: "192.168.10.11",
    CONF_USERNAME: "root",
    CONF_PASSWORD: "secret",
}

USER_INPUT_PORT_TOO_BIG = {
    CONF_HOST: "192.168.10.11",
    CONF_PORT: 255555,
    CONF_USERNAME: "root",
    CONF_PASSWORD: "secret",
    CONF_REALM: "pam",
    CONF_VERIFY_SSL: True,
}

USER_INPUT_PORT_TOO_SMALL = {
    CONF_HOST: "192.168.10.11",
    CONF_PORT: 0,
    CONF_USERNAME: "root",
    CONF_PASSWORD: "secret",
    CONF_REALM: "pam",
    CONF_VERIFY_SSL: True,
}

MOCK_GET_RESPONSE = [{"node": "node", "vmid": 100}, {"node": "node", "vmid": 100}]
MOCK_NODES = [
    {
        "maxcpu": 4,
        "id": "node/pve-01",
        "uptime": 9,
        "node": "pve-01",
        "cpu": 0.4,
        "maxmem": 33434685440,
        "maxdisk": 62297829376,
        "level": "",
        "status": "online",
        "disk": 59148279808,
        "mem": 12392038400,
        "type": "node",
    },
    {
        "maxcpu": 8,
        "id": "node/pve-02",
        "uptime": 15,
        "node": "pve-02",
        "cpu": 0.2,
        "maxmem": 33434685440,
        "maxdisk": 62297829376,
        "level": "",
        "status": "online",
        "disk": 59148279808,
        "mem": 12392038400,
        "type": "node",
    },
]
MOCK_QEMU = [
    {
        "netout": 0,
        "vmid": 100,
        "maxmem": 4294967296,
        "maxdisk": 34359738368,
        "diskwrite": 0,
        "diskread": 0,
        "mem": 0,
        "name": "HAOS",
        "cpus": 4,
        "cpu": 0,
        "disk": 0,
        "uptime": 0,
        "netin": 0,
        "status": "stopped",
    },
    {
        "maxmem": 4294967296,
        "vmid": 250,
        "netout": 0,
        "cpus": 4,
        "name": "Debian",
        "mem": 0,
        "diskread": 0,
        "diskwrite": 0,
        "maxdisk": 34359738368,
        "disk": 0,
        "uptime": 0,
        "cpu": 0,
        "status": "stopped",
        "netin": 0,
    },
    {
        "cpu": 0,
        "disk": 0,
        "uptime": 0,
        "template": 1,
        "netin": 0,
        "status": "stopped",
        "netout": 0,
        "vmid": 202,
        "maxmem": 4294967296,
        "diskwrite": 0,
        "diskread": 0,
        "maxdisk": 34359738368,
        "name": "HA Supervised",
        "mem": 0,
        "cpus": 4,
    },
    {
        "netin": 82718051184,
        "status": "running",
        "cpu": 0.177976600428671,
        "pid": 1218,
        "uptime": 97269,
        "disk": 0,
        "diskread": 0,
        "diskwrite": 0,
        "maxdisk": 34359738368,
        "name": "Win",
        "mem": 2822142607,
        "cpus": 4,
        "netout": 27209259499,
        "vmid": 101,
        "maxmem": 8589934592,
    },
    {
        "netout": 0,
        "vmid": 201,
        "maxmem": 4294967296,
        "diskwrite": 0,
        "maxdisk": 34359738368,
        "diskread": 0,
        "mem": 0,
        "name": "Debian11",
        "cpus": 4,
        "cpu": 0,
        "disk": 0,
        "uptime": 0,
        "netin": 0,
        "status": "stopped",
        "template": 1,
    },
    {
        "netin": 406772598,
        "status": "running",
        "cpu": 0.286605748457468,
        "pid": 2542,
        "disk": 0,
        "uptime": 97246,
        "maxdisk": 34359738368,
        "diskwrite": 0,
        "diskread": 0,
        "mem": 2264748745,
        "name": "HA",
        "cpus": 4,
        "netout": 402177510,
        "vmid": 151,
        "maxmem": 6442450944,
    },
    {
        "cpu": 0.00987164058693435,
        "disk": 0,
        "uptime": 97260,
        "pid": 1460,
        "status": "running",
        "netin": 654414276,
        "vmid": 102,
        "netout": 466534880,
        "maxmem": 4294967296,
        "name": "server-db",
        "mem": 2590602869,
        "diskwrite": 0,
        "diskread": 0,
        "maxdisk": 34359738368,
        "cpus": 4,
    },
]
MOCK_LXC = [
    {
        "cpus": 2,
        "name": "unifi",
        "mem": 687951872,
        "maxdisk": 8350298112,
        "diskwrite": 4816683008,
        "diskread": 1554276352,
        "type": "lxc",
        "maxmem": 2147483648,
        "vmid": "103",
        "netout": 633529454,
        "status": "running",
        "netin": 146440930,
        "swap": 0,
        "disk": 3018162176,
        "uptime": 97255,
        "pid": 1512,
        "maxswap": 536870912,
        "cpu": 0.00333741388592434,
    },
    {
        "cpus": 2,
        "maxdisk": 8350298112,
        "diskwrite": 7614971904,
        "diskread": 1428471808,
        "type": "lxc",
        "name": "uptimekuma",
        "mem": 171347968,
        "maxmem": 1073741824,
        "netout": 53433222,
        "vmid": "105",
        "netin": 169103530,
        "status": "running",
        "swap": 0,
        "pid": 1905,
        "disk": 1203150848,
        "uptime": 97252,
        "cpu": 0,
        "maxswap": 536870912,
    },
    {
        "maxmem": 1073741824,
        "vmid": "109",
        "netout": 68886401,
        "cpus": 2,
        "mem": 79491072,
        "name": "adguard",
        "diskread": 392511488,
        "diskwrite": 159055872,
        "type": "lxc",
        "maxdisk": 2040373248,
        "uptime": 97249,
        "disk": 611872768,
        "pid": 2264,
        "maxswap": 536870912,
        "cpu": 0,
        "status": "running",
        "netin": 61175305,
        "swap": 0,
    },
    {
        "name": "debian",
        "mem": 0,
        "diskwrite": 0,
        "maxdisk": 34359738368,
        "diskread": 0,
        "type": "lxc",
        "cpus": 4,
        "vmid": "110",
        "netout": 0,
        "maxmem": 8589934592,
        "swap": 0,
        "status": "stopped",
        "netin": 0,
        "maxswap": 536870912,
        "cpu": 0,
        "uptime": 0,
        "disk": 0,
    },
    {
        "swap": 0,
        "status": "stopped",
        "netin": 0,
        "maxswap": 536870912,
        "cpu": 0,
        "disk": 0,
        "uptime": 0,
        "mem": 0,
        "name": "mariadb",
        "diskread": 0,
        "diskwrite": 0,
        "type": "lxc",
        "maxdisk": 34359738368,
        "cpus": 2,
        "vmid": "111",
        "netout": 0,
        "maxmem": 2147483648,
    },
]


async def test_flow_ok(hass: HomeAssistant):
    """Test flow ok."""

    with patch("proxmoxer.ProxmoxResource.get", return_value=MOCK_GET_RESPONSE), patch(
        "proxmoxer.backends.https.ProxmoxHTTPAuth._get_new_tokens",
        return_value=None,
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT_OK
        )

        assert result["step_id"] == "node"
        assert result["type"] == FlowResultType.FORM
        assert "flow_id" in result

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=USER_INPUT_OK,
        )

        assert result["step_id"] == "selection_qemu_lxc"
        assert result["type"] == FlowResultType.FORM
        assert "flow_id" in result

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=USER_INPUT_OK,
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert "data" in result
        assert result["data"][CONF_HOST] == USER_INPUT_OK[CONF_HOST]
        assert result["data"][CONF_PORT] == USER_INPUT_OK[CONF_PORT]
        assert result["data"][CONF_USERNAME] == USER_INPUT_OK[CONF_USERNAME]
        assert result["data"][CONF_PASSWORD] == USER_INPUT_OK[CONF_PASSWORD]
        assert result["data"][CONF_REALM] == USER_INPUT_OK[CONF_REALM]
        assert result["data"][CONF_NODE][0] in USER_INPUT_OK[CONF_NODE]
        assert result["data"][CONF_QEMU][0] in USER_INPUT_OK[CONF_QEMU]
        assert result["data"][CONF_LXC][0] in USER_INPUT_OK[CONF_LXC]


async def test_flow_port_small(hass: HomeAssistant):
    """Test if port number too small."""

    with patch(
        "proxmoxer.backends.https.ProxmoxHTTPAuth._get_new_tokens", return_value=None
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT_PORT_TOO_SMALL
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"][CONF_PORT] == "invalid_port"


async def test_flow_port_big(hass: HomeAssistant):
    """Test if port number too big."""

    with patch(
        "proxmoxer.backends.https.ProxmoxHTTPAuth._get_new_tokens", return_value=None
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT_PORT_TOO_BIG
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"][CONF_PORT] == "invalid_port"


async def test_flow_auth_error(hass: HomeAssistant):
    """Test errors in case username or password are incorrect."""

    with patch(
        "homeassistant.components.proxmoxve.ProxmoxClient.build_client",
        side_effect=proxmoxer.backends.https.AuthenticationError("mock msg"),
        return_value=None,
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT_OK
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"][CONF_USERNAME] == "auth_error"


async def test_flow_cant_connect(hass: HomeAssistant):
    """Test errors in case the connection fails."""

    with patch(
        "homeassistant.components.proxmoxve.ProxmoxClient.build_client",
        side_effect=ConnectTimeout,
        return_value=None,
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT_OK
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"][CONF_HOST] == "cant_connect"


async def test_flow_ssl_error(hass: HomeAssistant):
    """Test errors in case the SSL certificare is not present or is not valid or is expired."""

    with patch(
        "homeassistant.components.proxmoxve.ProxmoxClient.build_client",
        side_effect=SSLError,
        return_value=None,
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT_OK
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"][CONF_VERIFY_SSL] == "ssl_rejection"


async def test_flow_unknown_exception(hass: HomeAssistant):
    """Test errors in case of an unknown exception occurs."""

    with patch(
        "homeassistant.components.proxmoxve.ProxmoxClient.build_client",
        side_effect=Exception,
        return_value=None,
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT_OK
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "general_error"


async def test_flow_import_ok(hass: HomeAssistant):
    """Test flow ok."""

    with patch("proxmoxer.ProxmoxResource.get", return_value=MOCK_GET_RESPONSE), patch(
        "proxmoxer.backends.https.ProxmoxHTTPAuth._get_new_tokens",
        return_value=None,
    ), patch(
        "homeassistant.components.proxmoxve.config_flow.ProxmoxVEConfigFlow._async_endpoint_exists",
        return_value=True,
    ):

        # imported config is identical to the one generated from config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT_OK
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_flow_import_ok_onlyrequired(hass: HomeAssistant):
    """Test flow ok."""

    with patch("proxmoxer.ProxmoxResource.get", return_value=MOCK_GET_RESPONSE), patch(
        "proxmoxer.backends.https.ProxmoxHTTPAuth._get_new_tokens",
        return_value=None,
    ), patch(
        "homeassistant.components.proxmoxve.config_flow.ProxmoxVEConfigFlow._async_endpoint_exists",
        return_value=True,
    ):

        # imported config is identical to the one generated from config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT_REQONLY
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_flow_import_error(hass: HomeAssistant):
    """Test flow ok."""

    with patch(
        "homeassistant.components.proxmoxve.ProxmoxClient.build_client",
        side_effect=Exception,
        return_value=None,
    ):

        # imported config is identical to the one generated from config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT_OK
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "import_failed"
