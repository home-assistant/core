"""Testing file for config flow ProxmoxVE."""
import logging

import proxmoxer
from requests.exceptions import ConnectTimeout, SSLError

from homeassistant.components.proxmoxve.const import (
    CONF_CONTAINERS,
    CONF_LXC,
    CONF_NODE,
    CONF_NODES,
    CONF_QEMU,
    CONF_REALM,
    CONF_VMS,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import (
    CONF_BASE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry, patch

_LOGGER = logging.getLogger(__name__)

USER_INPUT_OK = {
    CONF_HOST: "192.168.10.101",
    CONF_PORT: 8006,
    CONF_USERNAME: "root",
    CONF_PASSWORD: "secret",
    CONF_REALM: "pam",
    CONF_VERIFY_SSL: True,
    CONF_NODE: "pve",
    CONF_QEMU: [100, 101, 102],
    CONF_LXC: [201, 202, 203],
}

USER_INPUT_USER_HOST = {
    CONF_HOST: "192.168.10.101",
    CONF_PORT: 8006,
    CONF_USERNAME: "root",
    CONF_PASSWORD: "secret",
    CONF_REALM: "pam",
    CONF_VERIFY_SSL: True,
}
USER_INPUT_NODE = {
    CONF_NODE: "pve",
}
USER_INPUT_QEMU_LXC = {
    CONF_NODE: "pve",
    CONF_QEMU: [100, 101],
    CONF_LXC: [201, 202],
}
USER_INPUT_AUTH = {
    CONF_USERNAME: "root",
    CONF_PASSWORD: "secret",
    CONF_REALM: "pam",
}
USER_INPUT_OPTION_AUTH = {
    CONF_USERNAME: "root",
    CONF_PASSWORD: "secret",
    CONF_REALM: "pam",
    CONF_VERIFY_SSL: True,
}
USER_INPUT_IMPORT_OK = {
    CONF_HOST: "192.168.10.101",
    CONF_PORT: 8006,
    CONF_USERNAME: "root",
    CONF_PASSWORD: "secret",
    CONF_REALM: "pam",
    CONF_VERIFY_SSL: True,
    CONF_NODES: [
        {
            CONF_NODE: "pve",
            CONF_VMS: [100, 101],
            CONF_CONTAINERS: [201, 202],
        },
    ],
}

USER_INPUT_NOT_EXIST = {
    CONF_HOST: "192.168.10.101",
    CONF_PORT: 8006,
    CONF_USERNAME: "root",
    CONF_PASSWORD: "secret",
    CONF_REALM: "pam",
    CONF_VERIFY_SSL: True,
    CONF_NODES: [
        {
            CONF_NODE: "not_exist",
            CONF_VMS: [100, 101],
            CONF_CONTAINERS: [201, 202],
        },
    ],
}

USER_INPUT_PORT_TOO_BIG = {
    CONF_HOST: "192.168.10.101",
    CONF_PORT: 255555,
    CONF_USERNAME: "root",
    CONF_PASSWORD: "secret",
    CONF_REALM: "pam",
    CONF_VERIFY_SSL: True,
}

USER_INPUT_PORT_TOO_SMALL = {
    CONF_HOST: "192.168.10.101",
    CONF_PORT: 0,
    CONF_USERNAME: "root",
    CONF_PASSWORD: "secret",
    CONF_REALM: "pam",
    CONF_VERIFY_SSL: True,
}

MOCK_GET_RESPONSE = [
    {"node": "pve", "vmid": 100},
    {"node": "pve", "vmid": 101},
    {"node": "pve", "vmid": 102},
    {"node": "pve", "vmid": 200},
    {"node": "pve", "vmid": 201},
    {"node": "pve", "vmid": 202},
    {"node": "pve2", "vmid": 100},
    {"node": "pve2", "vmid": 201},
    {"node": "pve2", "vmid": 101},
]


async def test_flow_ok(hass: HomeAssistant):
    """Test flow ok."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "host"

    with patch("proxmoxer.ProxmoxResource.get", return_value=MOCK_GET_RESPONSE), patch(
        "proxmoxer.backends.https.ProxmoxHTTPAuth._get_new_tokens",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=USER_INPUT_USER_HOST,
        )

        assert result["step_id"] == "node"
        assert result["type"] == FlowResultType.FORM
        assert "flow_id" in result

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=USER_INPUT_NODE,
        )

        assert result["step_id"] == "selection_qemu_lxc"
        assert result["type"] == FlowResultType.FORM
        assert "flow_id" in result

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=USER_INPUT_QEMU_LXC,
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert "data" in result
        assert result["data"][CONF_HOST] == USER_INPUT_USER_HOST[CONF_HOST]


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


async def test_flow_already_configured(hass: HomeAssistant):
    """Test flow in case entry already configured."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=USER_INPUT_OK,
    )

    entry.add_to_hass(hass)

    with patch("proxmoxer.ProxmoxResource.get", return_value=MOCK_GET_RESPONSE), patch(
        "proxmoxer.backends.https.ProxmoxHTTPAuth._get_new_tokens",
        return_value=None,
    ), patch(
        "homeassistant.components.proxmoxve.config_flow.ProxmoxVEConfigFlow._async_endpoint_exists",
        return_value=True,
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=USER_INPUT_USER_HOST,
        )

        assert result["step_id"] == "node"
        assert result["type"] == FlowResultType.FORM
        assert "flow_id" in result

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=USER_INPUT_NODE,
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_flow_import_ok(hass: HomeAssistant):
    """Test import flow ok."""

    with patch("proxmoxer.ProxmoxResource.get", return_value=MOCK_GET_RESPONSE), patch(
        "proxmoxer.backends.https.ProxmoxHTTPAuth._get_new_tokens",
        return_value=None,
    ):

        # imported config is identical to the one generated from config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=USER_INPUT_IMPORT_OK,
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert "data" in result
        assert result["data"][CONF_HOST] == USER_INPUT_IMPORT_OK[CONF_HOST]


async def test_flow_import_error_port_small(hass: HomeAssistant):
    """Test flow import error port too small."""

    with patch(
        "homeassistant.components.proxmoxve.ProxmoxClient.build_client",
        return_value=None,
    ):

        # imported config is identical to the one generated from config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT_PORT_TOO_SMALL
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "import_failed"


async def test_flow_import_error_port_big(hass: HomeAssistant):
    """Test flow import error port too big."""

    with patch(
        "homeassistant.components.proxmoxve.ProxmoxClient.build_client",
        return_value=None,
    ):

        # imported config is identical to the one generated from config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT_PORT_TOO_BIG
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "import_failed"


async def test_flow_import_error_auth_error(hass: HomeAssistant):
    """Test import errors in case username or password are incorrect."""

    with patch(
        "homeassistant.components.proxmoxve.ProxmoxClient.build_client",
        side_effect=proxmoxer.backends.https.AuthenticationError("mock msg"),
        return_value=None,
    ):

        # imported config is identical to the one generated from config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT_IMPORT_OK
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "import_failed"


async def test_flow_import_error_ssl_rejection(hass: HomeAssistant):
    """Test import errors in case the SSL certificare is not present or is not valid or is expired."""

    with patch(
        "homeassistant.components.proxmoxve.ProxmoxClient.build_client",
        side_effect=SSLError,
        return_value=None,
    ):

        # imported config is identical to the one generated from config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT_USER_HOST
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "import_failed"


async def test_flow_import_error_cant_connect(hass: HomeAssistant):
    """Test import errors in case the connection fails."""

    with patch(
        "homeassistant.components.proxmoxve.ProxmoxClient.build_client",
        side_effect=ConnectTimeout,
        return_value=None,
    ):

        # imported config is identical to the one generated from config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT_IMPORT_OK
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "import_failed"


async def test_flow_import_error_general_error(hass: HomeAssistant):
    """Test import errors in case of an unknown exception occurs."""

    with patch(
        "homeassistant.components.proxmoxve.ProxmoxClient.build_client",
        side_effect=Exception,
        return_value=None,
    ):

        # imported config is identical to the one generated from config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT_IMPORT_OK
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "import_failed"


async def test_flow_import_error_node_not_exist(hass: HomeAssistant):
    """Test import error in case node not exist in Proxmox."""

    with patch("proxmoxer.ProxmoxResource.get", return_value=MOCK_GET_RESPONSE), patch(
        "homeassistant.components.proxmoxve.ProxmoxClient.build_client",
        return_value=None,
    ):

        # imported config is identical to the one generated from config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT_NOT_EXIST
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "import_failed"


async def test_flow_import_error_already_configured(hass: HomeAssistant):
    """Test import error in case entry already configured."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=USER_INPUT_IMPORT_OK,
    )

    entry.add_to_hass(hass)

    with patch("proxmoxer.ProxmoxResource.get", return_value=MOCK_GET_RESPONSE), patch(
        "proxmoxer.backends.https.ProxmoxHTTPAuth._get_new_tokens",
        return_value=None,
    ), patch(
        "homeassistant.components.proxmoxve.config_flow.ProxmoxVEConfigFlow._async_endpoint_exists",
        return_value=True,
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=USER_INPUT_IMPORT_OK,
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "import_failed"


async def test_step_reauth(hass: HomeAssistant) -> None:
    """Test the reauth flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=USER_INPUT_OK,
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert "flow_id" in result

    with patch(
        "homeassistant.components.proxmoxve.ProxmoxClient.build_client",
        return_value=True,
    ):
        result_auth_ok = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT_AUTH
        )
        assert result_auth_ok["type"] == FlowResultType.ABORT
        assert result_auth_ok["reason"] == "reauth_successful"

        assert len(hass.config_entries.async_entries()) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
    )

    with patch(
        "homeassistant.components.proxmoxve.ProxmoxClient.build_client",
        side_effect=proxmoxer.backends.https.AuthenticationError("mock msg"),
        return_value=None,
    ):
        result_auth_error = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT_AUTH
        )
        assert result_auth_error["type"] == FlowResultType.FORM
        assert result_auth_error["errors"][CONF_USERNAME] == "auth_error"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
    )

    with patch(
        "homeassistant.components.proxmoxve.ProxmoxClient.build_client",
        side_effect=SSLError,
        return_value=None,
    ):
        result_auth_ssl_rejection = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT_AUTH
        )
        assert result_auth_ssl_rejection["type"] == FlowResultType.FORM
        assert result_auth_ssl_rejection["errors"][CONF_BASE] == "ssl_rejection"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
    )

    with patch(
        "homeassistant.components.proxmoxve.ProxmoxClient.build_client",
        side_effect=ConnectTimeout,
        return_value=None,
    ):
        result_auth_ssl_rejectio = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT_AUTH
        )
        assert result_auth_ssl_rejectio["type"] == FlowResultType.FORM
        assert result_auth_ssl_rejectio["errors"][CONF_BASE] == "cant_connect"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
    )

    with patch(
        "homeassistant.components.proxmoxve.ProxmoxClient.build_client",
        side_effect=Exception,
        return_value=None,
    ):
        result_auth_ssl_rejectio = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT_AUTH
        )
        assert result_auth_ssl_rejectio["type"] == FlowResultType.FORM
        assert result_auth_ssl_rejectio["errors"][CONF_BASE] == "general_error"


async def test_options_flow_v1(hass: HomeAssistant):
    """Test options config flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test",
        data=USER_INPUT_OK,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.proxmoxve.async_setup_entry", return_value=True
    ):

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(entry.entry_id, data=None)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "host"

        result = await hass.config_entries.options.async_init(entry.entry_id)

        with patch(
            "homeassistant.components.proxmoxve.ProxmoxClient.build_client",
            side_effect=proxmoxer.backends.https.AuthenticationError("mock msg"),
            return_value=None,
        ):

            result_auth_error = await hass.config_entries.options.async_configure(
                result["flow_id"],
                user_input=USER_INPUT_OPTION_AUTH,
            )
            assert result_auth_error["type"] == FlowResultType.FORM
            assert result_auth_error["errors"][CONF_USERNAME] == "auth_error"

        with patch(
            "homeassistant.components.proxmoxve.ProxmoxClient.build_client",
            side_effect=SSLError,
            return_value=None,
        ):

            result_auth_ssl_rejection = (
                await hass.config_entries.options.async_configure(
                    result["flow_id"],
                    user_input=USER_INPUT_OPTION_AUTH,
                )
            )
            assert result_auth_ssl_rejection["type"] == FlowResultType.FORM
            assert (
                result_auth_ssl_rejection["errors"][CONF_VERIFY_SSL] == "ssl_rejection"
            )

        with patch(
            "homeassistant.components.proxmoxve.ProxmoxClient.build_client",
            side_effect=ConnectTimeout,
            return_value=None,
        ):

            result_auth_cant_connect = (
                await hass.config_entries.options.async_configure(
                    result["flow_id"],
                    user_input=USER_INPUT_OPTION_AUTH,
                )
            )
            assert result_auth_cant_connect["type"] == FlowResultType.FORM
            assert result_auth_cant_connect["errors"][CONF_HOST] == "cant_connect"

        with patch(
            "homeassistant.components.proxmoxve.ProxmoxClient.build_client",
            side_effect=Exception,
            return_value=None,
        ):

            result_auth_general_error = (
                await hass.config_entries.options.async_configure(
                    result["flow_id"],
                    user_input=USER_INPUT_OPTION_AUTH,
                )
            )
            assert result_auth_general_error["type"] == FlowResultType.FORM
            assert result_auth_general_error["errors"][CONF_BASE] == "general_error"

        with patch(
            "proxmoxer.ProxmoxResource.get", return_value=MOCK_GET_RESPONSE
        ), patch(
            "proxmoxer.backends.https.ProxmoxHTTPAuth._get_new_tokens",
            return_value=None,
        ):

            result = await hass.config_entries.options.async_configure(
                result["flow_id"],
                user_input=USER_INPUT_OPTION_AUTH,
            )

            assert result["step_id"] == "selection_qemu_lxc"
            assert result["type"] == FlowResultType.FORM
            assert "flow_id" in result

            result = await hass.config_entries.options.async_configure(
                result["flow_id"],
                user_input=USER_INPUT_QEMU_LXC,
            )

            assert result["type"] == FlowResultType.ABORT
            assert result["reason"] == "changes_successful"

            result = hass.config_entries.async_get_entry(entry.entry_id)
            assert entry.data[CONF_USERNAME] == USER_INPUT_OPTION_AUTH[CONF_USERNAME]
