"""Test the Geniushub config flow."""

from http import HTTPStatus
import socket
from unittest.mock import AsyncMock

from aiohttp import ClientConnectionError, ClientResponseError
import pytest
from pytest_homeassistant.common import MockConfigEntry, get_schema_suggested_value

from homeassistant.components.geniushub import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_local_flow(
    hass: HomeAssistant, mock_geniushub_client: AsyncMock
) -> None:
    """Test full local flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "local_api"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_api"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "10.0.0.130",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "10.0.0.130"
    assert result["data"] == {
        CONF_HOST: "10.0.0.130",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (socket.gaierror, "invalid_host"),
        (
            ClientResponseError(AsyncMock(), (), status=HTTPStatus.UNAUTHORIZED),
            "invalid_auth",
        ),
        (
            ClientResponseError(AsyncMock(), (), status=HTTPStatus.NOT_FOUND),
            "invalid_host",
        ),
        (TimeoutError, "cannot_connect"),
        (ClientConnectionError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_local_flow_exceptions(
    hass: HomeAssistant,
    mock_geniushub_client: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test local flow exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "local_api"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_api"

    mock_geniushub_client.request.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "10.0.0.130",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_geniushub_client.request.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "10.0.0.130",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_local_duplicate_data(
    hass: HomeAssistant,
    mock_geniushub_client: AsyncMock,
    mock_local_config_entry: MockConfigEntry,
) -> None:
    """Test local flow aborts on duplicate data."""
    mock_local_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "local_api"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_api"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "10.0.0.130",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_local_duplicate_mac(
    hass: HomeAssistant,
    mock_geniushub_client: AsyncMock,
    mock_local_config_entry: MockConfigEntry,
) -> None:
    """Test local flow aborts on duplicate MAC."""
    mock_local_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "local_api"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_api"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "10.0.0.131",
            CONF_USERNAME: "test-username1",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_cloud_flow(
    hass: HomeAssistant, mock_geniushub_client: AsyncMock
) -> None:
    """Test full cloud flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "cloud_api"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud_api"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TOKEN: "abcdef",
        },
    )
    # pylint: disable-next=home-assistant-tests-config-flow-unique-id
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Genius hub"
    assert result["data"] == {
        CONF_TOKEN: "abcdef",
    }


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (socket.gaierror, "invalid_host"),
        (
            ClientResponseError(AsyncMock(), (), status=HTTPStatus.UNAUTHORIZED),
            "invalid_auth",
        ),
        (
            ClientResponseError(AsyncMock(), (), status=HTTPStatus.NOT_FOUND),
            "invalid_host",
        ),
        (TimeoutError, "cannot_connect"),
        (ClientConnectionError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_cloud_flow_exceptions(
    hass: HomeAssistant,
    mock_geniushub_client: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test cloud flow exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "cloud_api"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud_api"

    mock_geniushub_client.request.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TOKEN: "abcdef",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_geniushub_client.request.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TOKEN: "abcdef",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_cloud_duplicate(
    hass: HomeAssistant,
    mock_geniushub_client: AsyncMock,
    mock_cloud_config_entry: MockConfigEntry,
) -> None:
    """Test cloud flow aborts on duplicate data."""
    mock_cloud_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "cloud_api"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud_api"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TOKEN: "abcdef",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_geniushub_client")
async def test_cloud_reauth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_cloud_config_entry: MockConfigEntry,
) -> None:
    """Test reauthentication of a cloud entry."""
    mock_cloud_config_entry.add_to_hass(hass)
    result = await mock_cloud_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "new-token"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_cloud_config_entry.data == {CONF_TOKEN: "new-token"}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_geniushub_client")
async def test_local_reauth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_local_config_entry: MockConfigEntry,
) -> None:
    """Test reauthentication of a local entry keeps the host."""
    mock_local_config_entry.add_to_hass(hass)
    result = await mock_local_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_USERNAME)
        == "test-username"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "new-username", CONF_PASSWORD: "new-password"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_local_config_entry.data == {
        CONF_HOST: "10.0.0.131",
        CONF_USERNAME: "new-username",
        CONF_PASSWORD: "new-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_local_reauth_wrong_account(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_geniushub_client: AsyncMock,
    mock_local_config_entry: MockConfigEntry,
) -> None:
    """Test local reauthentication aborts for a different hub."""
    mock_local_config_entry.add_to_hass(hass)
    result = await mock_local_config_entry.start_reauth_flow(hass)

    mock_geniushub_client.request.return_value = {"data": {"UID": "11:22:33:44:55:66"}}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "new-username", CONF_PASSWORD: "new-password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert mock_local_config_entry.data[CONF_PASSWORD] == "test-password"
    assert len(mock_setup_entry.mock_calls) == 0


REAUTH_EXCEPTIONS = [
    pytest.param(socket.gaierror, "invalid_host", id="gaierror"),
    pytest.param(
        ClientResponseError(AsyncMock(), (), status=HTTPStatus.UNAUTHORIZED),
        "invalid_auth",
        id="unauthorized",
    ),
    pytest.param(
        ClientResponseError(AsyncMock(), (), status=HTTPStatus.NOT_FOUND),
        "invalid_host",
        id="not_found",
    ),
    pytest.param(TimeoutError, "cannot_connect", id="timeout"),
    pytest.param(ClientConnectionError, "cannot_connect", id="connection_error"),
    pytest.param(Exception, "unknown", id="unknown"),
]


@pytest.mark.parametrize(("exception", "error"), REAUTH_EXCEPTIONS)
async def test_cloud_reauth_exceptions(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_geniushub_client: AsyncMock,
    mock_cloud_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test cloud reauthentication errors and recovery."""
    mock_cloud_config_entry.add_to_hass(hass)
    result = await mock_cloud_config_entry.start_reauth_flow(hass)

    mock_geniushub_client.request.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "new-token"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    mock_geniushub_client.request.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "new-token"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_cloud_config_entry.data == {CONF_TOKEN: "new-token"}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(("exception", "error"), REAUTH_EXCEPTIONS)
async def test_local_reauth_exceptions(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_geniushub_client: AsyncMock,
    mock_local_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test local reauthentication errors and recovery."""
    mock_local_config_entry.add_to_hass(hass)
    result = await mock_local_config_entry.start_reauth_flow(hass)

    mock_geniushub_client.request.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "new-username", CONF_PASSWORD: "new-password"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}
    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_USERNAME)
        == "new-username"
    )
    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_PASSWORD) is None
    )

    mock_geniushub_client.request.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "new-username", CONF_PASSWORD: "new-password"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_local_config_entry.data == {
        CONF_HOST: "10.0.0.131",
        CONF_USERNAME: "new-username",
        CONF_PASSWORD: "new-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1
