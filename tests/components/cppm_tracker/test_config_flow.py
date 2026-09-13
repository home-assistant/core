"""Tests for the Aruba ClearPass (cppm_tracker) config flow."""

from unittest.mock import AsyncMock, MagicMock

import pytest
import requests

from homeassistant.components.cppm_tracker.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_CLIENT_ID, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_CONFIG, MOCK_HOST

from tests.common import MockConfigEntry

USER_INPUT = {
    CONF_HOST: MOCK_HOST,
    CONF_CLIENT_ID: "client",
    CONF_API_KEY: "secret",
}


async def test_user_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_clearpass: MagicMock
) -> None:
    """Test the user flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_HOST
    assert result["data"] == MOCK_CONFIG


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_clearpass: MagicMock
) -> None:
    """Test the user flow recovers after a connection error."""
    mock_clearpass.side_effect = requests.exceptions.ConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_clearpass.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("side_effect", "access_token"),
    [
        pytest.param(KeyError("access_token"), "token", id="rejected"),
        pytest.param(None, None, id="no_token"),
    ],
)
async def test_user_flow_invalid_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_clearpass: MagicMock,
    side_effect: Exception | None,
    access_token: str | None,
) -> None:
    """Test the user flow reports invalid credentials and then recovers."""
    mock_clearpass.side_effect = side_effect
    mock_clearpass.return_value.access_token = access_token

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_clearpass.side_effect = None
    mock_clearpass.return_value.access_token = "token"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_clearpass: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the user flow aborts when the host is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_clearpass: MagicMock
) -> None:
    """Test importing a YAML configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_HOST
    assert result["data"] == MOCK_CONFIG


async def test_import_flow_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_clearpass: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the import flow aborts when the host is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "access_token"),
    [
        pytest.param(requests.exceptions.ConnectionError, "token", id="cannot_connect"),
        pytest.param(KeyError("access_token"), "token", id="invalid_auth"),
    ],
)
async def test_import_flow_aborts_on_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_clearpass: MagicMock,
    side_effect: Exception,
    access_token: str | None,
) -> None:
    """Test the import flow aborts when ClearPass rejects the configuration."""
    mock_clearpass.side_effect = side_effect
    mock_clearpass.return_value.access_token = access_token

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
