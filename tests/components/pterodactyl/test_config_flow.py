"""Test the Pterodactyl config flow."""

from pydactyl import PterodactylClient
from pydactyl.exceptions import ClientConfigError, PterodactylApiError
from pydactyl.responses import PaginatedResponse
import pytest

from homeassistant.components.pterodactyl.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    TEST_SERVER,
    TEST_SERVER_LIST_DATA,
    TEST_SERVER_UTILIZATION,
    TEST_URL,
    TEST_USER_INPUT,
)

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_pterodactyl")
async def test_full_flow(
    hass: HomeAssistant, mock_pterodactyl: PterodactylClient
) -> None:
    """Test full flow without errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_pterodactyl.client.servers.list_servers.return_value = PaginatedResponse(
        mock_pterodactyl, "client", TEST_SERVER_LIST_DATA
    )
    mock_pterodactyl.client.servers.get_server.return_value = TEST_SERVER
    mock_pterodactyl.client.servers.get_server_utilization.return_value = (
        TEST_SERVER_UTILIZATION
    )

    result2 = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"],
        user_input=TEST_USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_URL
    assert result2["data"] == TEST_USER_INPUT


@pytest.mark.parametrize(
    "exception_type",
    [
        ClientConfigError,
        PterodactylApiError,
    ],
)
@pytest.mark.usefixtures("mock_pterodactyl")
async def test_recovery_after_api_error(
    hass: HomeAssistant, exception_type, mock_pterodactyl: PterodactylClient
) -> None:
    """Test recovery after an API error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_pterodactyl.client.servers.list_servers.side_effect = exception_type

    result2 = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"],
        user_input=TEST_USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    mock_pterodactyl.reset_mock(side_effect=True)
    mock_pterodactyl.client.servers.list_servers.return_value = PaginatedResponse(
        mock_pterodactyl, "client", TEST_SERVER_LIST_DATA
    )
    mock_pterodactyl.client.servers.get_server.return_value = TEST_SERVER
    mock_pterodactyl.client.servers.get_server_utilization.return_value = (
        TEST_SERVER_UTILIZATION
    )

    result3 = await hass.config_entries.flow.async_configure(
        flow_id=result2["flow_id"], user_input=TEST_USER_INPUT
    )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == TEST_URL
    assert result3["data"] == TEST_USER_INPUT


@pytest.mark.usefixtures("mock_config_entry", "mock_pterodactyl")
async def test_service_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pterodactyl: PterodactylClient,
) -> None:
    """Test config flow abort if the Pterodactyl server is already configured."""
    mock_config_entry.add_to_hass(hass)

    mock_pterodactyl.client.servers.list_servers.return_value = PaginatedResponse(
        mock_pterodactyl, "client", TEST_SERVER_LIST_DATA
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=TEST_USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
