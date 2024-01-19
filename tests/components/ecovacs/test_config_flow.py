"""Test Ecovacs config flow."""
from typing import Any
from unittest.mock import AsyncMock

from aiohttp import ClientError
from deebot_client.exceptions import InvalidAuthenticationError
import pytest

from homeassistant.components.ecovacs.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_USERNAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir

from .const import IMPORT_DATA, VALID_ENTRY_DATA

from tests.common import MockConfigEntry


async def _test_user_flow(hass: HomeAssistant) -> dict[str, Any]:
    """Test config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=VALID_ENTRY_DATA,
    )


async def test_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_authenticator_authenticate: AsyncMock,
) -> None:
    """Test the user config flow."""
    result = await _test_user_flow(hass)
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == VALID_ENTRY_DATA[CONF_USERNAME]
    assert result["data"] == VALID_ENTRY_DATA
    mock_setup_entry.assert_called()
    mock_authenticator_authenticate.assert_called()


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (ClientError, "cannot_connect"),
        (InvalidAuthenticationError, "invalid_auth"),
        (Exception, "unknown"),
    ],
)
async def test_user_flow_error(
    hass: HomeAssistant,
    side_effect: Exception,
    reason: str,
    mock_setup_entry: AsyncMock,
    mock_authenticator_authenticate: AsyncMock,
) -> None:
    """Test handling invalid connection."""

    mock_authenticator_authenticate.side_effect = side_effect

    result = await _test_user_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": reason}
    mock_authenticator_authenticate.assert_called()
    mock_setup_entry.assert_not_called()

    mock_authenticator_authenticate.reset_mock(side_effect=True)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=VALID_ENTRY_DATA,
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == VALID_ENTRY_DATA[CONF_USERNAME]
    assert result["data"] == VALID_ENTRY_DATA
    mock_setup_entry.assert_called()
    mock_authenticator_authenticate.assert_called()


async def test_import_flow(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_setup_entry: AsyncMock,
    mock_authenticator_authenticate: AsyncMock,
) -> None:
    """Test importing yaml config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=IMPORT_DATA.copy(),
    )
    mock_authenticator_authenticate.assert_called()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == VALID_ENTRY_DATA[CONF_USERNAME]
    assert result["data"] == VALID_ENTRY_DATA
    assert (HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}") in issue_registry.issues
    mock_setup_entry.assert_called()


async def test_import_flow_already_configured(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test importing yaml config where entry already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=VALID_ENTRY_DATA)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=IMPORT_DATA.copy(),
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert (HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}") in issue_registry.issues


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (ClientError, "cannot_connect"),
        (InvalidAuthenticationError, "invalid_auth"),
        (Exception, "unknown"),
    ],
)
async def test_import_flow_error(
    hass: HomeAssistant,
    side_effect: Exception,
    reason: str,
    issue_registry: ir.IssueRegistry,
    mock_authenticator_authenticate: AsyncMock,
) -> None:
    """Test handling invalid connection."""
    mock_authenticator_authenticate.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=IMPORT_DATA.copy(),
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == reason
    assert (
        DOMAIN,
        f"deprecated_yaml_import_issue_{reason}",
    ) in issue_registry.issues
    mock_authenticator_authenticate.assert_called()
