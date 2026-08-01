"""Tests for Quantum Gateway config flow."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from requests import RequestException

from homeassistant.components.quantum_gateway.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_CONFIG

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_scanner: MagicMock
) -> None:
    """Test a successful config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_CONFIG[CONF_HOST]
    assert result["data"] == MOCK_CONFIG


@pytest.mark.parametrize(
    ("side_effect", "success_init", "failure_type"),
    [
        (
            RequestException("example error"),
            True,
            "cannot_connect",
        ),
        (
            None,
            False,
            "invalid_auth",
        ),
    ],
)
async def test_user_flow_failure(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_scanner: MagicMock,
    side_effect: RequestException | None,
    success_init: bool,
    failure_type: str,
) -> None:
    """Test a config flow failure."""
    mock_scanner.side_effect = side_effect
    mock_scanner.return_value.success_init = success_init

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": failure_type}

    mock_scanner.side_effect = None
    mock_scanner.return_value.success_init = True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_entry_exists(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_scanner: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test user flow aborts when entry already exists."""
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


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_scanner: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a reauth flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM

    mock_scanner.return_value.success_init = False

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_scanner.return_value.success_init = True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "new password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new password"


async def test_import_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_scanner: MagicMock
) -> None:
    """Test a successful import."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_CONFIG[CONF_HOST]
    assert result["data"] == MOCK_CONFIG


@pytest.mark.parametrize(
    ("side_effect", "success_init", "failure_type"),
    [
        (
            RequestException("example error"),
            True,
            "cannot_connect",
        ),
        (
            None,
            False,
            "invalid_auth",
        ),
    ],
)
async def test_import_flow_failure(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_scanner: MagicMock,
    side_effect: RequestException | None,
    success_init: bool,
    failure_type: str,
) -> None:
    """Test a failed import."""
    mock_scanner.side_effect = side_effect
    mock_scanner.return_value.success_init = success_init

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == failure_type


async def test_import_flow_entry_exists(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_scanner: MagicMock,
    mock_config_entry,
) -> None:
    """Test import flow aborts when entry already exists."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
