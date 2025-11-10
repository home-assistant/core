"""Test the Logitech Squeezebox config flow."""

from http import HTTPStatus
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

USER_INPUT = {
    CONF_HOST: HOST,
}

EDIT_INPUT = {
    CONF_HOST: HOST,
    CONF_PORT: PORT,
    CONF_USERNAME: "",
    CONF_PASSWORD: "",
    CONF_HTTPS: False,
}


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


async def test_user_flow_duplicate_entry(
    hass: HomeAssistant,
    mock_server,
    mock_setup_entry,
    mock_config_entry,
    mock_discover_success,
) -> None:
    """Test user-initiated flow with existing entry (duplicate)."""

    entry = mock_config_entry
    entry.add_to_hass(hass)

    mock_server.async_query.side_effect = query_success
    mock_server.http_status = HTTPStatus.OK

    with (
        patch(
            "homeassistant.components.squeezebox.config_flow.async_discover",
            mock_discover_success,
        ),
        patch("homeassistant.components.squeezebox.config_flow.TIMEOUT", 0.1),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "no_server_found"}


@pytest.mark.parametrize(
    ("discover_fixture", "expect_error", "expect_entry"),
    [
        ("mock_discover_success", None, True),
        ("mock_failed_discover_fixture", "no_server_found", False),
    ],
)
async def test_user_flow_discovery_variants(
    hass: HomeAssistant,
    mock_server,
    mock_setup_entry,
    mock_discover_success,
    mock_discover_failure,
    discover_fixture,
    expect_error,
    expect_entry,
) -> None:
    """Test user-initiated flow variants: normal discovery and timeout."""

    discover_func = (
        mock_discover_success
        if discover_fixture == "mock_discover_success"
        else mock_discover_failure
    )

    mock_server.async_query.side_effect = lambda *args, **kwargs: {"uuid": UUID}
    mock_server.http_status = HTTPStatus.OK

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

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], EDIT_INPUT
    )

    if expect_entry:
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == HOST
        assert result2["data"] == EDIT_INPUT
        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


async def query_success(*args, **kwargs):
    """Simulate successful query returning UUID."""
    return {"uuid": UUID}


async def query_cannot_connect(*args, **kwargs):
    """Simulate connection failure."""
    return False  # Simulate failure; set status separately


async def query_unauthorized(*args, **kwargs):
    """Simulate unauthorized access."""
    return False  # Simulate failure; set status separately


class SqueezeError(Exception):
    """Custom exception to simulate unexpected query failure."""


async def query_exception(*args, **kwargs):
    """Simulate unexpected exception."""
    raise SqueezeError("Unexpected error")


@pytest.mark.parametrize(
    ("discovery_data", "query_behavior", "http_status", "expect_error"),
    [
        (
            {CONF_HOST: HOST, CONF_PORT: PORT, "uuid": UUID},
            query_success,
            HTTPStatus.OK,
            None,
        ),  # UUID present, success
        (
            {CONF_HOST: HOST, CONF_PORT: PORT, CONF_HTTPS: False},
            query_unauthorized,
            HTTPStatus.UNAUTHORIZED,
            "invalid_auth",
        ),  # No UUID, unauthorized
        (
            {CONF_HOST: HOST, CONF_PORT: PORT, CONF_HTTPS: False},
            query_cannot_connect,
            HTTPStatus.BAD_GATEWAY,
            "cannot_connect",
        ),  # No UUID, connection failure
        (
            {CONF_HOST: HOST, CONF_PORT: PORT, CONF_HTTPS: False},
            query_exception,
            None,
            "unknown",
        ),  # No UUID, unexpected exception
    ],
)
async def test_discovery_flow_variants(
    hass: HomeAssistant,
    mock_server,
    mock_setup_entry,
    discovery_data,
    query_behavior,
    http_status,
    expect_error,
) -> None:
    """Test integration discovery flow with and without UUID."""

    # Inject behavior into mock_server
    mock_server.async_query.side_effect = query_behavior
    mock_server.http_status = http_status

    # Start flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data=discovery_data,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "edit"

    # First configure attempt
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

    if expect_error:
        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": expect_error}

        # Recovery attempt
        mock_server.async_query.side_effect = query_success
        mock_server.http_status = HTTPStatus.OK

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
        result = result2

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


async def test_dhcp_discovery_flow_success(
    hass: HomeAssistant,
    mock_server,
    mock_setup_entry,
    mock_discover_success,
    dhcp_info,
) -> None:
    """Test DHCP discovery flow with successful discovery and query."""

    # Inject successful query behavior
    mock_server.async_query.side_effect = query_success
    mock_server.http_status = HTTPStatus.OK

    with (
        patch(
            "homeassistant.components.squeezebox.config_flow.async_discover",
            mock_discover_success,
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
            result["flow_id"], USER_INPUT
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "edit"
    else:
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "edit"

    # Final configure step
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], EDIT_INPUT
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "1.1.1.1"
    assert result2["data"] == EDIT_INPUT


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


@pytest.mark.parametrize(
    ("query_behavior", "http_status", "expected_error"),
    [
        (query_unauthorized, HTTPStatus.UNAUTHORIZED, "invalid_auth"),
        (query_cannot_connect, HTTPStatus.BAD_GATEWAY, "cannot_connect"),
        (query_exception, None, "unknown"),
    ],
)
async def test_flow_errors_and_recovery(
    hass: HomeAssistant,
    mock_setup_entry,
    mock_server,
    query_behavior,
    http_status,
    expected_error,
    patch_discover,
) -> None:
    """Test config flow error handling and recovery."""

    # Start flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["step_id"] == "edit"

    # Inject error
    mock_server.async_query.side_effect = query_behavior
    mock_server.http_status = http_status

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], EDIT_INPUT
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": expected_error}

    # Recover
    mock_server.async_query.side_effect = None
    mock_server.async_query.return_value = {"uuid": UUID}

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"], EDIT_INPUT
    )
    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == HOST
    assert result3["data"] == EDIT_INPUT
