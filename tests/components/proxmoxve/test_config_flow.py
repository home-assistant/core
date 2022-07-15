"""Testing file for config flow ProxmoxVE."""
import proxmoxer
from requests.exceptions import ConnectTimeout, SSLError

from homeassistant.components.proxmoxve.const import CONF_REALM, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import patch

USER_INPUT_OK = {
    CONF_HOST: "192.168.10.11",
    CONF_PORT: 8006,
    CONF_USERNAME: "root",
    CONF_PASSWORD: "secret",
    CONF_REALM: "pam",
    CONF_VERIFY_SSL: True,
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


async def test_flow_ok(hass: HomeAssistant):
    """Test flow ok."""

    with patch("proxmoxer.ProxmoxResource.get", return_value=MOCK_GET_RESPONSE), patch(
        "proxmoxer.backends.https.ProxmoxHTTPAuth._get_new_tokens",
        return_value=None,
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT_OK
        )

        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["data"][CONF_HOST] == USER_INPUT_OK[CONF_HOST]


async def test_flow_port_small(hass: HomeAssistant):
    """Test if port number too small."""

    with patch(
        "proxmoxer.backends.https.ProxmoxHTTPAuth._get_new_tokens", return_value=None
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT_PORT_TOO_SMALL
        )

        assert result["type"] == RESULT_TYPE_FORM
        assert result["errors"][CONF_PORT] == "invalid_port"


async def test_flow_port_big(hass: HomeAssistant):
    """Test if port number too big."""

    with patch(
        "proxmoxer.backends.https.ProxmoxHTTPAuth._get_new_tokens", return_value=None
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT_PORT_TOO_BIG
        )

        assert result["type"] == RESULT_TYPE_FORM
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

        assert result["type"] == RESULT_TYPE_FORM
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

        assert result["type"] == RESULT_TYPE_FORM
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

        assert result["type"] == RESULT_TYPE_FORM
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

        assert result["type"] == RESULT_TYPE_FORM
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

        assert result["type"] == RESULT_TYPE_ABORT
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

        assert result["type"] == RESULT_TYPE_ABORT
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

        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "import_failed"
