"""Test Ecovacs config flow."""
from typing import Any
from unittest.mock import Mock, patch

import pytest
from sucks import EcoVacsAPI

from homeassistant.components.ecovacs.const import CONF_CONTINENT, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry

_USER_INPUT = {
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_COUNTRY: "it",
    CONF_CONTINENT: "eu",
}


async def _test_config_flow(hass: HomeAssistant) -> dict[str, Any]:
    """Test config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=_USER_INPUT,
    )


async def test_full_user_flow(hass: HomeAssistant, mock_setup_entry) -> None:
    """Test the full user configuration flow."""
    with patch(
        "homeassistant.components.ecovacs.config_flow.EcoVacsAPI",
        return_value=Mock(spec_set=EcoVacsAPI),
    ):
        result = await _test_config_flow(hass)
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == _USER_INPUT[CONF_USERNAME]
        assert result["data"] == _USER_INPUT


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (ValueError, "invalid_auth"),
        (Exception, "unknown"),
    ],
)
async def test_flow_error(
    hass: HomeAssistant, side_effect: Exception, reason: str, mock_setup_entry
) -> None:
    """Test handling invalid connection."""
    with patch(
        "homeassistant.components.ecovacs.config_flow.EcoVacsAPI",
        return_value=Mock(spec_set=EcoVacsAPI),
    ) as mock_ecovacs:
        mock_ecovacs.side_effect = side_effect

        result = await _test_config_flow(hass)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": reason}


async def test_import_flow(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, mock_setup_entry
) -> None:
    """Test importing yaml config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=_USER_INPUT,
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == _USER_INPUT[CONF_USERNAME]
    assert result["data"] == _USER_INPUT
    assert len(issue_registry.issues) == 1
    # assert (DOMAIN, expected_issue) in issue_registry.issues


async def test_import_flow_already_exists(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test importing yaml config where entry already exists."""
    entry = MockConfigEntry(domain=DOMAIN, data=_USER_INPUT)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=_USER_INPUT,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(issue_registry.issues) == 1
