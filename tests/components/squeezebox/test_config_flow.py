"""Test the Logitech Squeezebox config flow."""

from unittest.mock import patch

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


async def test_user_form(
    hass: HomeAssistant,
    mock_setup_entry,
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
    assert len(mock_setup_entry.mock_calls) == 1


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


async def test_user_form_timeout(
    hass: HomeAssistant,
    mock_async_query,
    mock_setup_entry,
    mock_discover_success,
    mock_failed_discover_fixture,
) -> None:
    """Test we handle server search timeout and allow manual entry."""

    # First flow: simulate timeout
    with (
        patch(
            "homeassistant.components.squeezebox.config_flow.async_discover",
            mock_failed_discover_fixture,
        ),
        patch("homeassistant.components.squeezebox.config_flow.TIMEOUT", 0.1),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "no_server_found"}

    # Second flow: simulate successful discovery
    mock_async_query("uuid")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit"

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


async def test_user_form_duplicate(
    hass: HomeAssistant,
    mock_discover_success,
    mock_setup_entry,
    mock_config_entry,
) -> None:
    """Test duplicate discovered servers are skipped."""

    entry = mock_config_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_server_found"}


async def test_form_invalid_auth(
    hass: HomeAssistant,
    mock_setup_entry,
    mock_async_query,
    mock_discover_success,
    patch_async_query_unauthorized,
) -> None:
    """Test we handle invalid auth."""

    # Initial flow with valid UUID discovery
    mock_async_query("uuid")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit"

    # Simulate invalid auth
    with patch(
        "homeassistant.components.squeezebox.config_flow.Server.async_query",
        new=patch_async_query_unauthorized,
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

    # Retry with blank credentials
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


async def test_form_validate_exception(
    hass: HomeAssistant,
    mock_async_query,
    mock_setup_entry,
    mock_discover_success,
) -> None:
    """Test we handle exception and recover."""

    # Initial flow setup
    mock_async_query("uuid")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit"

    # Simulate exception during validation
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

    # Retry with normal behavior
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


async def test_form_cannot_connect(
    hass: HomeAssistant,
    mock_async_query,
    mock_setup_entry,
) -> None:
    """Test we handle cannot connect error, then succeed after retry."""

    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "edit"}
    )
    assert result["type"] is FlowResultType.FORM

    # First attempt: simulate cannot connect
    mock_async_query("false")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Second attempt: simulate a successful connection
    mock_async_query("uuid")
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
    assert result["context"]["unique_id"] == UUID


async def test_discovery_with_uuid(
    hass: HomeAssistant,
    mock_async_query,
    mock_setup_entry,
) -> None:
    """Test handling of discovered server, then completing the flow."""

    mock_async_query("uuid")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={CONF_HOST: HOST, CONF_PORT: PORT, "uuid": UUID},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit"

    mock_async_query("uuid")
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
    assert result["context"]["unique_id"] == UUID


async def test_discovery_no_uuid(
    hass: HomeAssistant,
    mock_async_query,
    mock_setup_entry,
    patch_async_query_unauthorized,
) -> None:
    """Test discovery without uuid first fails, then succeeds when uuid is available."""

    with patch(
        "pysqueezebox.Server.async_query",
        new=patch_async_query_unauthorized,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={CONF_HOST: HOST, CONF_PORT: PORT, CONF_HTTPS: False},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit"

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

    mock_async_query("uuid")
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
    assert result["context"]["unique_id"] == UUID


async def test_dhcp_discovery(
    hass: HomeAssistant,
    mock_async_query,
    mock_discover_success,
    mock_setup_entry,
) -> None:
    """Test we can process discovery from DHCP and complete the flow."""

    mock_async_query("uuid")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip=HOST,
            macaddress="aabbccddeeff",
            hostname="any",
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit"

    mock_async_query("uuid")
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
    assert result["context"]["unique_id"] == UUID


async def test_dhcp_discovery_no_server_found(
    hass: HomeAssistant,
    mock_setup_entry,
    mock_failed_discover_fixture,
    mock_async_query_failure,
    dhcp_info,
) -> None:
    """Test we can handle DHCP discovery when no server is found."""

    # Initial discovery fails
    with (
        patch(
            "homeassistant.components.squeezebox.config_flow.async_discover",
            mock_failed_discover_fixture,
        ),
        patch("homeassistant.components.squeezebox.config_flow.TIMEOUT", 0.1),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp_info,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Provide host to move into edit step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit"

    # Final configure attempt fails due to query failure
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
    assert result["errors"] == {"base": "cannot_connect"}


async def test_dhcp_discovery_existing_player(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    dhcp_info: DhcpServiceInfo,
) -> None:
    """Test that we properly ignore known players during DHCP discovery."""

    # Register a squeezebox media_player entity with the same MAC unique_id
    entity_registry.async_get_or_create(
        domain="media_player",
        platform=DOMAIN,
        unique_id=format_mac("aabbccddeeff"),
    )

    # Fire DHCP discovery for the same MAC
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=dhcp_info,
    )

    # Flow should abort because the player is already known
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
