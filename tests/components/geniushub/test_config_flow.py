"""Test the Geniushub config flow."""

from http import HTTPStatus
import socket
from unittest.mock import AsyncMock

from aiohttp import ClientConnectionError, ClientResponseError
import pytest

from homeassistant.components.geniushub import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_local_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_geniushub_client: AsyncMock,
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
async def test_local_flow_exceptions(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
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


async def test_full_cloud_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_geniushub_client: AsyncMock,
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
async def test_cloud_flow_exceptions(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
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
