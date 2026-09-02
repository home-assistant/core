"""Tests for the DD-WRT config flow."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.ddwrt.const import DOMAIN
from homeassistant.components.ddwrt.router import DdWrtAuthError, DdWrtConnectionError
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_CONFIG, MOCK_HOST

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_router: MagicMock
) -> None:
    """Test a successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"DD-WRT ({MOCK_HOST})"
    assert result["data"] == MOCK_CONFIG


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_router: MagicMock
) -> None:
    """Test the user flow surfaces a connection error and then recovers."""
    mock_router.return_value.get_clients.side_effect = DdWrtConnectionError("fail")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_router.return_value.get_clients.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_router: MagicMock
) -> None:
    """Test the user flow reports invalid auth distinctly from cannot connect."""
    mock_router.return_value.get_clients.side_effect = DdWrtAuthError("bad creds")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_router: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the user flow aborts when the host is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_router: MagicMock
) -> None:
    """Test a successful import flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"DD-WRT ({MOCK_HOST})"
    assert result["data"] == MOCK_CONFIG


async def test_import_flow_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_router: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the import flow aborts when the host is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_router: MagicMock
) -> None:
    """Test the import flow aborts on a connection error."""
    mock_router.return_value.get_clients.side_effect = DdWrtConnectionError("fail")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
