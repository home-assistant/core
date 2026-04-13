"""Test the Squeezebox config flow."""

from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, MagicMock

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

from .conftest import SERVER_UUIDS

from tests.common import MockConfigEntry

# Use the same UUIDs defined in the conftest
TEST_UUID = SERVER_UUIDS[0]


async def test_manual_setup(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_server: AsyncMock
) -> None:
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
    assert result["result"].unique_id == TEST_UUID
    assert result["title"] == "1.2.3.4"
    assert result["data"][CONF_HOST] == "1.2.3.4"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("query_return", "http_status", "expected_error"),
    [
        (False, HTTPStatus.UNAUTHORIZED, "invalid_auth"),
        (False, HTTPStatus.NOT_FOUND, "cannot_connect"),
        ({"no_uuid": True}, HTTPStatus.OK, "missing_uuid"),
    ],
)
async def test_manual_setup_data_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_server: AsyncMock,
    query_return: Any,
    http_status: HTTPStatus,
    expected_error: str,
) -> None:
    """Test data-driven error states during manual setup and recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "edit"}
    )

    mock_server.async_query.return_value = query_return
    mock_server.http_status = http_status

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_PORT: 9000}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == expected_error

    mock_server.async_query.return_value = {"uuid": TEST_UUID}
    mock_server.http_status = HTTPStatus.OK

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 9000,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TEST_UUID
    assert len(mock_setup_entry.mock_calls) == 1


async def test_manual_setup_exception_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_server: AsyncMock,
) -> None:
    """Test exception error state during manual setup and recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "edit"}
    )

    mock_server.async_query.side_effect = Exception("Connection fail")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_PORT: 9000}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"

    mock_server.async_query.side_effect = None
    mock_server.async_query.return_value = {"uuid": TEST_UUID}
    mock_server.http_status = HTTPStatus.OK

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 9000,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TEST_UUID
    assert len(mock_setup_entry.mock_calls) == 1


async def test_manual_setup_recovery(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_server: AsyncMock
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
    assert result["result"].unique_id == TEST_UUID
    assert result["title"] == "1.2.3.4"
    assert result["data"][CONF_HOST] == "1.2.3.4"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate_setup(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_server: AsyncMock,
    mock_config_entry: MockConfigEntry,
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


async def test_discovery_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_server: AsyncMock,
    mock_discover: MagicMock,
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
    assert result["result"].unique_id == TEST_UUID
    assert result["title"] == "1.1.1.1"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_discovery_flow_edit_discovered_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_server: AsyncMock,
    mock_discover: MagicMock,
) -> None:
    """Test the successful outcome of the edit_discovered step."""
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

    mock_server.http_status = HTTPStatus.OK
    mock_server.async_query.side_effect = [False, {"uuid": TEST_UUID}]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "admin", CONF_PASSWORD: "password"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1.1.1.1"
    assert result["data"][CONF_HOST] == "1.1.1.1"
    assert result["data"][CONF_USERNAME] == "admin"
    assert result["data"][CONF_PASSWORD] == "password"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "http_status", "expected_error"),
    [
        (False, HTTPStatus.UNAUTHORIZED, "invalid_auth"),
        (False, HTTPStatus.NOT_FOUND, "cannot_connect"),
        ({"no_uuid": True}, HTTPStatus.OK, "missing_uuid"),
        (Exception("Test error"), None, "unknown"),
    ],
)
async def test_discovery_flow_edit_discovered_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_server: AsyncMock,
    mock_discover: MagicMock,
    side_effect: Any,
    http_status: HTTPStatus | None,
    expected_error: str,
) -> None:
    """Test all error outcomes of the edit_discovered step."""
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

    mock_server.http_status = http_status
    mock_server.async_query.side_effect = [False, side_effect]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "admin", CONF_PASSWORD: "password"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == expected_error


async def test_discovery_flow_failed(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_discover: MagicMock
) -> None:
    """Test discovery flow when no servers are found."""

    async def _failed_discover(callback: Any) -> list:
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


async def test_discovery_ignores_existing(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_discover: MagicMock,
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
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_server: AsyncMock
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
    assert result["result"].unique_id == TEST_UUID
    assert result["title"] == "1.2.3.4"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_integration_discovery_no_uuid(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_server: AsyncMock
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
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_server: AsyncMock
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
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_server: AsyncMock
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
    assert result["result"].unique_id == TEST_UUID
    assert result["title"] == "1.2.3.4"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_unknown_player(
    hass: HomeAssistant, dhcp_info: dict[str, Any]
) -> None:
    """Test DHCP discovery of an unconfigured player routes to user setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=dhcp_info,
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"


async def test_dhcp_known_player(
    hass: HomeAssistant, dhcp_info: dict[str, Any], mock_config_entry: MockConfigEntry
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
