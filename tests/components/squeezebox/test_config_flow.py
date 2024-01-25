"""Test the Logitech Squeezebox config flow."""
from http import HTTPStatus
from unittest.mock import patch

from pysqueezebox import Server

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.components.squeezebox.const import CONF_HTTPS, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

HOST = "1.1.1.1"
HOST2 = "2.2.2.2"
PORT = 9000
UUID = "test-uuid"
UNKNOWN_ERROR = "1234"


async def mock_discover(_discovery_callback):
    """Mock discovering a Logitech Media Server."""
    _discovery_callback(Server(None, HOST, PORT, uuid=UUID))


async def mock_failed_discover(_discovery_callback):
    """Mock unsuccessful discovery by doing nothing."""


async def patch_async_query_unauthorized(self, *args):
    """Mock an unauthorized query."""
    self.http_status = HTTPStatus.UNAUTHORIZED
    return False


async def test_user_form(hass: HomeAssistant) -> None:
    """Test user-initiated flow, including discovery and the edit step."""
    with patch(
        "pysqueezebox.Server.async_query",
        return_value={"uuid": UUID},
    ), patch(
        "homeassistant.components.squeezebox.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.squeezebox.config_flow.async_discover", mock_discover
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "edit"
        assert CONF_HOST in result["data_schema"].schema
        for key in result["data_schema"].schema:
            if key == CONF_HOST:
                assert key.description == {"suggested_value": HOST}

        # test the edit step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_HTTPS: False,
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == HOST
        assert result["data"] == {
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
            CONF_HTTPS: False,
        }

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


async def test_user_form_timeout(hass: HomeAssistant) -> None:
    """Test we handle server search timeout."""
    with patch(
        "homeassistant.components.squeezebox.config_flow.async_discover",
        mock_failed_discover,
    ), patch("homeassistant.components.squeezebox.config_flow.TIMEOUT", 0.1):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "no_server_found"}

        # simulate manual input of host
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST2}
        )
        assert result2["type"] == FlowResultType.FORM
        assert result2["step_id"] == "edit"
        assert CONF_HOST in result2["data_schema"].schema
        for key in result2["data_schema"].schema:
            if key == CONF_HOST:
                assert key.description == {"suggested_value": HOST2}


async def test_user_form_duplicate(hass: HomeAssistant) -> None:
    """Test duplicate discovered servers are skipped."""
    with patch(
        "homeassistant.components.squeezebox.config_flow.async_discover",
        mock_discover,
    ), patch("homeassistant.components.squeezebox.config_flow.TIMEOUT", 0.1), patch(
        "homeassistant.components.squeezebox.async_setup_entry",
        return_value=True,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=UUID,
            data={CONF_HOST: HOST, CONF_PORT: PORT, CONF_HTTPS: False},
        )
        await hass.config_entries.async_add(entry)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "no_server_found"}


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "edit"}
    )

    async def patch_async_query(self, *args):
        self.http_status = HTTPStatus.UNAUTHORIZED
        return False

    with patch("pysqueezebox.Server.async_query", new=patch_async_query):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "edit"}
    )

    with patch(
        "pysqueezebox.Server.async_query",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_discovery(hass: HomeAssistant) -> None:
    """Test handling of discovered server."""
    with patch(
        "pysqueezebox.Server.async_query",
        return_value={"uuid": UUID},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={CONF_HOST: HOST, CONF_PORT: PORT, "uuid": UUID},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "edit"


async def test_discovery_no_uuid(hass: HomeAssistant) -> None:
    """Test handling of discovered server with unavailable uuid."""
    with patch("pysqueezebox.Server.async_query", new=patch_async_query_unauthorized):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={CONF_HOST: HOST, CONF_PORT: PORT, CONF_HTTPS: False},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "edit"


async def test_dhcp_discovery(hass: HomeAssistant) -> None:
    """Test we can process discovery from dhcp."""
    with patch(
        "pysqueezebox.Server.async_query",
        return_value={"uuid": UUID},
    ), patch(
        "homeassistant.components.squeezebox.config_flow.async_discover", mock_discover
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip="1.1.1.1",
                macaddress="AA:BB:CC:DD:EE:FF",
                hostname="any",
            ),
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "edit"


async def test_dhcp_discovery_no_server_found(hass: HomeAssistant) -> None:
    """Test we can handle dhcp discovery when no server is found."""
    with patch(
        "homeassistant.components.squeezebox.config_flow.async_discover",
        mock_failed_discover,
    ), patch("homeassistant.components.squeezebox.config_flow.TIMEOUT", 0.1):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip="1.1.1.1",
                macaddress="AA:BB:CC:DD:EE:FF",
                hostname="any",
            ),
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"


async def test_dhcp_discovery_existing_player(hass: HomeAssistant) -> None:
    """Test that we properly ignore known players during dhcp discover."""
    with patch(
        "homeassistant.helpers.entity_registry.EntityRegistry.async_get_entity_id",
        return_value="test_entity",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip="1.1.1.1",
                macaddress="AA:BB:CC:DD:EE:FF",
                hostname="any",
            ),
        )
        assert result["type"] == FlowResultType.ABORT
