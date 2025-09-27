"""Test the Logitech Squeezebox config flow."""

from http import HTTPStatus
from unittest.mock import patch

from pysqueezebox import Server
import pytest

from homeassistant import config_entries
from homeassistant.components.squeezebox.const import (
    CONF_BROWSE_LIMIT,
    CONF_HTTPS,
    CONF_VOLUME_STEP,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from tests.common import MockConfigEntry

HOST = "1.1.1.1"
HOST2 = "2.2.2.2"
PORT = 9000
UUID = "test-uuid"
UNKNOWN_ERROR = "1234"
BROWSE_LIMIT = 10
VOLUME_STEP = 1


@pytest.fixture
def mock_async_query():
    """Fixture to patch Server.async_query with different behaviours."""

    with patch("pysqueezebox.Server.async_query") as mock:

        def _set_behavior(mode: str):
            if mode == "uuid":
                mock.return_value = {"uuid": UUID}
                mock.side_effect = None
            elif mode == "false":
                mock.return_value = False
                mock.side_effect = None
            elif mode == "unauthorized":
                # delegate to your existing helper
                mock.side_effect = patch_async_query_unauthorized
                mock.return_value = None
            else:
                raise ValueError(f"Unknown mode: {mode}")
            return mock

        yield _set_behavior


async def mock_discover(_discovery_callback):
    """Mock discovering a Logitech Media Server."""
    _discovery_callback(Server(None, HOST, PORT, uuid=UUID))


async def mock_failed_discover(_discovery_callback):
    """Mock unsuccessful discovery by doing nothing."""


async def patch_async_query_unauthorized(self, *args):
    """Mock an unauthorized query."""
    self.http_status = HTTPStatus.UNAUTHORIZED
    return False


async def test_user_form(
    hass: HomeAssistant,
    mock_async_setup_entry,
    mock_async_query,
    mock_discover_success,
) -> None:
    """Test user-initiated flow, including discovery and the edit step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit"
    assert CONF_HOST in result["data_schema"].schema
    for key in result["data_schema"].schema:
        if key == CONF_HOST:
            assert key.description == {"suggested_value": HOST}

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
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_PORT: PORT,
        CONF_USERNAME: "",
        CONF_PASSWORD: "",
        CONF_HTTPS: False,
    }

    await hass.async_block_till_done()
    assert len(mock_async_setup_entry.mock_calls) == 1


async def test_options_form(hass: HomeAssistant) -> None:
    """Test we can configure options."""
    entry = MockConfigEntry(
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
            CONF_HTTPS: False,
        },
        unique_id=UUID,
        domain=DOMAIN,
        options={CONF_BROWSE_LIMIT: 1000, CONF_VOLUME_STEP: 5},
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # simulate manual input of options
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_BROWSE_LIMIT: BROWSE_LIMIT, CONF_VOLUME_STEP: VOLUME_STEP},
    )

    # put some meaningful asserts here
    assert result["type"] is FlowResultType.CREATE_ENTRY

    assert result["data"] == {
        CONF_BROWSE_LIMIT: BROWSE_LIMIT,
        CONF_VOLUME_STEP: VOLUME_STEP,
    }


async def test_user_form_timeout(hass: HomeAssistant) -> None:
    """Test we handle server search timeout."""
    with (
        patch(
            "homeassistant.components.squeezebox.config_flow.async_discover",
            mock_failed_discover,
        ),
        patch("homeassistant.components.squeezebox.config_flow.TIMEOUT", 0.1),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "no_server_found"}

        # simulate manual input of host
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST2}
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "edit"
        assert CONF_HOST in result2["data_schema"].schema
        for key in result2["data_schema"].schema:
            if key == CONF_HOST:
                assert key.description == {"suggested_value": HOST2}


async def test_user_form_duplicate(hass: HomeAssistant) -> None:
    """Test duplicate discovered servers are skipped."""
    with (
        patch(
            "homeassistant.components.squeezebox.config_flow.async_discover",
            mock_discover,
        ),
        patch("homeassistant.components.squeezebox.config_flow.TIMEOUT", 0.1),
        patch(
            "homeassistant.components.squeezebox.async_setup_entry",
            return_value=True,
        ),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=UUID,
            data={CONF_HOST: HOST, CONF_PORT: PORT, CONF_HTTPS: False},
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "no_server_found"}


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""

    async def patch_async_query(self, *args):
        self.http_status = HTTPStatus.UNAUTHORIZED
        return False

    with (
        patch(
            "pysqueezebox.Server.async_query",
            return_value={"uuid": UUID},
        ),
        patch(
            "homeassistant.components.squeezebox.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.squeezebox.config_flow.async_discover",
            mock_discover,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "edit"

        with patch(
            "homeassistant.components.squeezebox.config_flow.Server.async_query",
            new=patch_async_query,
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

            assert result["type"] is FlowResultType.FORM
            assert result["errors"] == {"base": "invalid_auth"}

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
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == HOST
        assert result["data"] == {
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
            CONF_HTTPS: False,
        }


async def test_form_validate_exception(hass: HomeAssistant, mock_async_query) -> None:
    """Test we handle exception and recover."""

    mock_async_query("uuid")
    with (
        patch(
            "homeassistant.components.squeezebox.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.squeezebox.config_flow.async_discover",
            mock_discover,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit"

    # Force an exception on validation
    with patch(
        "homeassistant.components.squeezebox.config_flow.Server.async_query",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_HTTPS: False,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}

    # Retry with normal behaviour
    mock_async_query("uuid")
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
            CONF_HTTPS: False,
        },
    )

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == HOST
    assert result3["data"] == {
        CONF_HOST: HOST,
        CONF_PORT: PORT,
        CONF_USERNAME: "",
        CONF_PASSWORD: "",
        CONF_HTTPS: False,
    }


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error, then succeed after retry."""

    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "edit"}
    )
    assert result["type"] is FlowResultType.FORM

    # First attempt: simulate cannot connect
    with patch(
        "pysqueezebox.Server.async_query",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
            },
        )

    # We should still be in a form, with an error
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Second attempt: simulate a successful connection
    with patch(
        "pysqueezebox.Server.async_query",
        return_value={"uuid": UUID},
    ):
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

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == HOST  # the flow uses host as title
        assert result["data"] == {
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
            CONF_HTTPS: False,
        }
        assert result["context"]["unique_id"] == UUID


async def test_discovery(hass: HomeAssistant) -> None:
    """Test handling of discovered server, then completing the flow."""

    # Initial discovery: server responds with a uuid
    with patch(
        "pysqueezebox.Server.async_query",
        return_value={"uuid": UUID},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={CONF_HOST: HOST, CONF_PORT: PORT, "uuid": UUID},
        )

    # Discovery puts us into the edit step
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit"

    # Complete the edit step with user input
    with patch(
        "pysqueezebox.Server.async_query",
        return_value={"uuid": UUID},
    ):
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

    # Flow should now complete with a config entry
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_PORT: PORT,
        CONF_USERNAME: "",
        CONF_PASSWORD: "",
        CONF_HTTPS: False,
    }
    assert result["context"]["unique_id"] == UUID


async def test_discovery_no_uuid(hass: HomeAssistant) -> None:
    """Test discovery without uuid first fails, then succeeds when uuid is available."""

    # Initial discovery: no uuid returned
    with patch(
        "pysqueezebox.Server.async_query",
        new=patch_async_query_unauthorized,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={CONF_HOST: HOST, CONF_PORT: PORT, CONF_HTTPS: False},
        )

    # Flow shows the edit form
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit"

    # First attempt to complete: still no uuid → error on the form
    with patch(
        "pysqueezebox.Server.async_query",
        new=patch_async_query_unauthorized,
    ):
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

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Second attempt: now the server responds with a uuid
    with patch(
        "pysqueezebox.Server.async_query",
        return_value={"uuid": UUID},
    ):
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

    # Flow should now complete successfully
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_PORT: PORT,
        CONF_USERNAME: "",
        CONF_PASSWORD: "",
        CONF_HTTPS: False,
    }
    assert result["context"]["unique_id"] == UUID


async def test_dhcp_discovery(hass: HomeAssistant) -> None:
    """Test we can process discovery from dhcp and complete the flow."""

    with (
        patch(
            "pysqueezebox.Server.async_query",
            return_value={"uuid": UUID},
        ),
        patch(
            "homeassistant.components.squeezebox.config_flow.async_discover",
            mock_discover,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DhcpServiceInfo(
                ip=HOST,
                macaddress="aabbccddeeff",
                hostname="any",
            ),
        )

    # DHCP discovery puts us into the edit step
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit"

    # Complete the edit step with user input
    with patch(
        "pysqueezebox.Server.async_query",
        return_value={"uuid": UUID},
    ):
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

    # Flow should now complete with a config entry
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_PORT: PORT,
        CONF_USERNAME: "",
        CONF_PASSWORD: "",
        CONF_HTTPS: False,
    }
    assert result["context"]["unique_id"] == UUID


async def test_dhcp_discovery_no_server_found(hass: HomeAssistant) -> None:
    """Test we can handle dhcp discovery when no server is found."""

    with (
        patch(
            "homeassistant.components.squeezebox.config_flow.async_discover",
            mock_failed_discover,
        ),
        patch("homeassistant.components.squeezebox.config_flow.TIMEOUT", 0.1),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DhcpServiceInfo(
                ip=HOST,
                macaddress="aabbccddeeff",
                hostname="any",
            ),
        )

    # First step: user form with only host
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Provide just the host to move into edit step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit"

    # Now try to complete the edit step with full schema
    with patch(
        "homeassistant.components.squeezebox.config_flow.async_discover",
        mock_failed_discover,
    ):
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit"
    assert result["errors"] == {"base": "unknown"}


async def test_dhcp_discovery_existing_player(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that we properly ignore known players during dhcp discover."""

    # Register a squeezebox media_player entity with the same MAC unique_id
    entity_registry.async_get_or_create(
        domain="media_player",
        platform=DOMAIN,
        unique_id=format_mac("aabbccddeeff"),
    )

    # Now fire a DHCP discovery for the same MAC
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="1.1.1.1",
            macaddress="aabbccddeeff",
            hostname="any",
        ),
    )

    # Because the player is already known, the flow should abort
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
