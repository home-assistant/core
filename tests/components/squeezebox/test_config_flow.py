"""Test the Logitech Squeezebox config flow."""

from unittest.mock import patch

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


@pytest.mark.parametrize(
    ("discover_fixture", "has_existing_entry", "expect_error", "expect_entry"),
    [
        ("mock_discover_success", False, None, True),  # normal discovery
        ("mock_failed_discover_fixture", False, "no_server_found", False),  # timeout
        ("mock_discover_success", True, "no_server_found", False),  # duplicate
    ],
)
async def test_user_flow_variants(
    hass: HomeAssistant,
    mock_async_query,
    mock_setup_entry,
    mock_config_entry,
    mock_discover_success,
    mock_discover_failure,
    discover_fixture,
    has_existing_entry,
    expect_error,
    expect_entry,
) -> None:
    """Test user-initiated flow variants: discovery, timeout, and duplicate."""

    # Add existing config entry if needed
    if has_existing_entry:
        entry = mock_config_entry()
        entry.add_to_hass(hass)

    # Select discovery behavior
    discover_func = (
        mock_discover_success
        if discover_fixture == "mock_discover_success"
        else mock_discover_failure
    )

    with (
        patch(
            "homeassistant.components.squeezebox.config_flow.async_discover",
            discover_func,
        ),
        patch("homeassistant.components.squeezebox.config_flow.TIMEOUT", 0.1),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    if expect_error:
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": expect_error}
        return

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "edit"
    assert CONF_HOST in result["data_schema"].schema
    for key in result["data_schema"].schema:
        if key == CONF_HOST:
            assert key.description == {"suggested_value": HOST}

    mock_async_query("uuid")
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

    if expect_entry:
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == HOST
        assert result2["data"] == {
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
            CONF_HTTPS: False,
        }
        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("query_mode", "expected_error"),
    [
        ("false", "cannot_connect"),
        ("unauthorized", "invalid_auth"),
        ("exception", "unknown"),
    ],
)
async def test_flow_errors_and_recovery(
    hass: HomeAssistant,
    mock_async_query,
    mock_setup_entry,
    config_flow_input,
    query_mode,
    expected_error,
) -> None:
    """Test config flow error handling and recovery."""

    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    # Ensure we reach the 'edit' step
    if result["step_id"] == "user":
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            config_flow_input("user"),
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "edit"

    # Simulate error
    mock_async_query(query_mode)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        config_flow_input("edit"),
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Simulate recovery
    mock_async_query("uuid")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        config_flow_input("edit"),
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "1.1.1.1"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 9000,
        CONF_USERNAME: "",
        CONF_PASSWORD: "",
        CONF_HTTPS: False,
    }


@pytest.mark.parametrize(
    ("discovery_data", "initial_patch", "expect_error"),
    [
        (
            {CONF_HOST: HOST, CONF_PORT: PORT, "uuid": UUID},
            None,
            None,
        ),  # UUID present, success
        (
            {CONF_HOST: HOST, CONF_PORT: PORT, CONF_HTTPS: False},
            "unauthorized",
            "invalid_auth",
        ),  # No UUID, initial failure
    ],
)
async def test_discovery_flow_variants(
    hass: HomeAssistant,
    mock_async_query,
    mock_setup_entry,
    patch_async_query_unauthorized,
    discovery_data,
    initial_patch,
    expect_error,
) -> None:
    """Test integration discovery flow with and without UUID."""

    # Patch initial query if needed
    if initial_patch == "unauthorized":
        with patch(
            "pysqueezebox.Server.async_query", new=patch_async_query_unauthorized
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
                data=discovery_data,
            )
    else:
        mock_async_query("uuid")
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=discovery_data,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "edit"

    # First configure attempt
    if expect_error:
        with patch(
            "pysqueezebox.Server.async_query", new=patch_async_query_unauthorized
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
        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": expect_error}

        # Recovery attempt
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
        result = result3
    else:
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

    # Final assertions
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_PORT: PORT,
        CONF_USERNAME: "",
        CONF_PASSWORD: "",
        CONF_HTTPS: False,
    }
    assert result["context"]["unique_id"] == UUID


@pytest.mark.parametrize(
    ("discover_success", "query_mode", "expected_type", "expected_error"),
    [
        (True, "uuid", FlowResultType.CREATE_ENTRY, None),
        (False, "false", FlowResultType.FORM, "cannot_connect"),
    ],
)
async def test_dhcp_discovery_flow(
    hass: HomeAssistant,
    mock_async_query,
    mock_setup_entry,
    config_flow_input,
    mock_discover_success,
    mock_discover_failure,
    dhcp_info,
    discover_success,
    query_mode,
    expected_type,
    expected_error,
) -> None:
    """Test DHCP discovery flow with success and failure modes."""

    # Select discovery behavior
    discover_func = mock_discover_success if discover_success else mock_discover_failure

    with (
        patch(
            "homeassistant.components.squeezebox.config_flow.async_discover",
            discover_func,
        ),
        patch("homeassistant.components.squeezebox.config_flow.TIMEOUT", 0.1),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp_info,
        )

    # Handle initial step
    if result["step_id"] == "user":
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            config_flow_input("user"),
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "edit"
    else:
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "edit"

    # Simulate error or success
    mock_async_query(query_mode)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        config_flow_input("edit"),
    )

    assert result2["type"] == expected_type

    if expected_type == FlowResultType.CREATE_ENTRY:
        assert result2["title"] == "1.1.1.1"
        assert result2["data"] == {
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 9000,
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
            CONF_HTTPS: False,
        }
    else:
        assert result2["errors"] == {"base": expected_error}


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
