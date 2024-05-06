"""Test AfterShip config flow."""
from unittest.mock import AsyncMock, patch

from pyaftership import AfterShipException

from homeassistant.components.aftership.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry


async def test_full_user_flow(hass: HomeAssistant, mock_setup_entry) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with patch(
        "homeassistant.components.aftership.config_flow.AfterShip",
        return_value=AsyncMock(),
    ) as mock_aftership:
        mock_aftership.return_value.trackings.return_value.list.return_value = {}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "mock-api-key",
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "AfterShip"
        assert result["data"] == {
            CONF_API_KEY: "mock-api-key",
        }


async def test_flow_cannot_connect(hass: HomeAssistant, mock_setup_entry) -> None:
    """Test handling invalid connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with patch(
        "homeassistant.components.aftership.config_flow.AfterShip",
        return_value=AsyncMock(),
    ) as mock_aftership:
        mock_aftership.side_effect = AfterShipException
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "mock-api-key",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.aftership.config_flow.AfterShip",
        return_value=AsyncMock(),
    ) as mock_aftership:
        mock_aftership.return_value.trackings.return_value.list.return_value = {}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "mock-api-key",
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "AfterShip"
        assert result["data"] == {
            CONF_API_KEY: "mock-api-key",
        }


async def test_import_flow(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, mock_setup_entry
) -> None:
    """Test importing yaml config."""

    with patch(
        "homeassistant.components.aftership.config_flow.AfterShip",
        return_value=AsyncMock(),
    ) as mock_aftership:
        mock_aftership.return_value.trackings.return_value.list.return_value = {}
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_API_KEY: "yaml-api-key"},
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "AfterShip"
        assert result["data"] == {
            CONF_API_KEY: "yaml-api-key",
        }
    assert len(issue_registry.issues) == 1


async def test_import_flow_already_exists(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test importing yaml config where entry already exists."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "yaml-api-key"})
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_API_KEY: "yaml-api-key"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(issue_registry.issues) == 1
