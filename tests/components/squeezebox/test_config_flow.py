"""Test the Squeezebox config flow."""

from http import HTTPStatus

import pytest

from homeassistant import config_entries
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.squeezebox.const import (
    CONF_BROWSE_LIMIT,
    CONF_SERVER_LIST,
    CONF_VOLUME_STEP,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

TEST_UUID = "12345678-1234-1234-1234-123456789012"


async def test_manual_setup(hass: HomeAssistant, mock_setup_entry, mock_server) -> None:
    """Test we can finish a manual setup successfully."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "edit"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit"

    mock_server.async_query.return_value = {"uuid": TEST_UUID}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4", CONF_PORT: 9000},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1.2.3.4"
    assert result["data"][CONF_HOST] == "1.2.3.4"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("query_return", "http_status", "side_effect", "expected_error"),
    [
        (False, HTTPStatus.UNAUTHORIZED, None, "invalid_auth"),
        (False, HTTPStatus.NOT_FOUND, None, "cannot_connect"),
        ({"no_uuid": True}, HTTPStatus.OK, None, "missing_uuid"),
        (None, None, Exception, "unknown"),
    ],
)
async def test_manual_setup_errors(
    hass: HomeAssistant,
    mock_setup_entry,
    mock_server,
    query_return,
    http_status,
    side_effect,
    expected_error,
) -> None:
    """Test all possible error states during manual setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "edit"}
    )

    mock_server.async_query.return_value = query_return
    mock_server.http_status = http_status
    if side_effect:
        mock_server.async_query.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4", CONF_PORT: 9000},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == expected_error


async def test_manual_setup_recovery(
    hass: HomeAssistant, mock_setup_entry, mock_server
) -> None:
    """Test manual setup error recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "edit"}
    )

    mock_server.async_query.return_value = False
    mock_server.http_status = HTTPStatus.UNAUTHORIZED

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4", CONF_PORT: 9000},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit"
    assert result["errors"]["base"] == "invalid_auth"

    mock_server.async_query.return_value = {"uuid": TEST_UUID}
    mock_server.http_status = HTTPStatus.OK

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 9000,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "correct_password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1.2.3.4"
    assert result["data"][CONF_HOST] == "1.2.3.4"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate_setup(
    hass: HomeAssistant, mock_setup_entry, mock_server, mock_config_entry
) -> None:
    """Test abort if setting up an already configured server."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "edit"}
    )

    mock_server.async_query.return_value = {"uuid": TEST_UUID}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4", CONF_PORT: 9000},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_discover_timeout")
async def test_discovery_flow_success(
    hass: HomeAssistant,
    mock_setup_entry,
    mock_server,
    mock_discover,
) -> None:
    """Test discovery flow where default connect succeeds immediately."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "start_discovery"}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_discovery"

    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "choose_server"

    mock_server.async_query.return_value = {"uuid": TEST_UUID}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SERVER_LIST: "1.1.1.1"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1.1.1.1"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_discover_timeout")
@pytest.mark.parametrize(
    ("query_return", "http_status", "side_effect", "expected_type", "expected_result"),
    [
        ({"uuid": TEST_UUID}, HTTPStatus.OK, None, FlowResultType.CREATE_ENTRY, None),
        (False, HTTPStatus.UNAUTHORIZED, None, FlowResultType.FORM, "invalid_auth"),
        (False, HTTPStatus.NOT_FOUND, None, FlowResultType.FORM, "cannot_connect"),
        ({"no_uuid": True}, HTTPStatus.OK, None, FlowResultType.FORM, "missing_uuid"),
        (None, None, Exception("Test error"), FlowResultType.FORM, "unknown"),
    ],
)
async def test_discovery_flow_edit_discovered_outcomes(
    hass: HomeAssistant,
    mock_setup_entry,
    mock_server,
    mock_discover,
    query_return,
    http_status,
    side_effect,
    expected_type,
    expected_result,
) -> None:
    """Test all possible outcomes of the edit_discovered step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "start_discovery"}
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    mock_server.http_status = HTTPStatus.UNAUTHORIZED
    mock_server.async_query.return_value = False

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SERVER_LIST: "1.1.1.1"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit_discovered"

    mock_server.http_status = http_status
    if side_effect:
        mock_server.async_query.side_effect = [False, side_effect]
    else:
        mock_server.async_query.side_effect = [False, query_return]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "admin", CONF_PASSWORD: "password"}
    )

    assert result["type"] is expected_type
    if expected_type is FlowResultType.FORM:
        assert result["errors"]["base"] == expected_result
    else:
        assert result["title"] == "1.1.1.1"
        assert result["data"][CONF_HOST] == "1.1.1.1"
        assert result["data"][CONF_USERNAME] == "admin"
        assert result["data"][CONF_PASSWORD] == "password"
        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_discover_timeout")
async def test_discovery_flow_failed(
    hass: HomeAssistant, mock_setup_entry, mock_discover
) -> None:
    """Test discovery flow when no servers are found."""

    async def _failed_discover(callback):
        return []

    mock_discover.side_effect = _failed_discover

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "start_discovery"}
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "discovery_failed"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "edit"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit"


@pytest.mark.usefixtures("mock_discover_timeout")
async def test_discovery_ignores_existing(
    hass: HomeAssistant,
    mock_setup_entry,
    mock_config_entry,
    mock_discover,
) -> None:
    """Test discovery properly ignores a server that's already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "start_discovery"}
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "discovery_failed"


async def test_integration_discovery(
    hass: HomeAssistant, mock_setup_entry, mock_server
) -> None:
    """Test integration discovery flow with a provided UUID."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={CONF_HOST: "1.2.3.4", CONF_PORT: 9000, "uuid": TEST_UUID},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit_integration_discovered"

    mock_server.async_query.return_value = {"uuid": TEST_UUID}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "admin", CONF_PASSWORD: "password"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1.2.3.4"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_integration_discovery_no_uuid(
    hass: HomeAssistant, mock_setup_entry, mock_server
) -> None:
    """Test integration discovery flow without a UUID."""
    mock_server.async_query.return_value = {"uuid": TEST_UUID}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={CONF_HOST: "1.2.3.4", CONF_PORT: 9000},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit_integration_discovered"


async def test_integration_discovery_no_uuid_fails(
    hass: HomeAssistant, mock_setup_entry, mock_server
) -> None:
    """Test integration discovery flow routes to form when connection fails."""
    mock_server.async_query.return_value = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={CONF_HOST: "1.2.3.4", CONF_PORT: 9000},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit_integration_discovered"


async def test_integration_discovery_edit_recovery(
    hass: HomeAssistant, mock_setup_entry, mock_server
) -> None:
    """Test editing an integration discovery returns errors and can recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={CONF_HOST: "1.2.3.4", CONF_PORT: 9000, "uuid": TEST_UUID},
    )

    mock_server.async_query.return_value = False
    mock_server.http_status = HTTPStatus.UNAUTHORIZED

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "admin", CONF_PASSWORD: "wrongpassword"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit_integration_discovered"
    assert result["errors"]["base"] == "invalid_auth"

    mock_server.async_query.return_value = {"uuid": TEST_UUID}
    mock_server.http_status = HTTPStatus.OK

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "admin", CONF_PASSWORD: "correctpassword"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1.2.3.4"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_unknown_player(hass: HomeAssistant, dhcp_info) -> None:
    """Test DHCP discovery of an unconfigured player routes to user setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=dhcp_info,
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"


async def test_dhcp_known_player(
    hass: HomeAssistant, dhcp_info, mock_config_entry
) -> None:
    """Test DHCP discovery aborts if player is already registered."""
    mock_config_entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        MP_DOMAIN, DOMAIN, "aa:bb:cc:dd:ee:ff", config_entry=mock_config_entry
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=dhcp_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the options flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_BROWSE_LIMIT: 500, CONF_VOLUME_STEP: 5},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {
        CONF_BROWSE_LIMIT: 500,
        CONF_VOLUME_STEP: 5,
    }
