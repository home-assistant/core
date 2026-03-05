"""Tests for the Hetzner Cloud config flow."""

from __future__ import annotations

from unittest.mock import MagicMock

from hcloud import APIException
import pytest

from homeassistant.components.hetzner.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_hcloud_config_flow")
async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_TOKEN: "test-api-token-12345"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Hetzner Cloud"
    assert result["data"] == {CONF_API_TOKEN: "test-api-token-12345"}


async def test_user_flow_invalid_auth(
    hass: HomeAssistant, mock_hcloud_config_flow: MagicMock
) -> None:
    """Test user flow with invalid authentication and recovery."""
    mock_hcloud_config_flow.load_balancers.get_all.side_effect = APIException(
        code=401, message="Unauthorized", details={}
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_TOKEN: "bad-token"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Recover from error
    mock_hcloud_config_flow.load_balancers.get_all.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_TOKEN: "good-token"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_unknown_error(
    hass: HomeAssistant, mock_hcloud_config_flow: MagicMock
) -> None:
    """Test user flow with unknown error and recovery."""
    mock_hcloud_config_flow.load_balancers.get_all.side_effect = RuntimeError(
        "Unexpected"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_TOKEN: "test-token"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    # Recover from error
    mock_hcloud_config_flow.load_balancers.get_all.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_TOKEN: "test-token"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_hcloud_config_flow")
async def test_reauth_flow_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful reauth flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_TOKEN: "new-api-token"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_TOKEN] == "new-api-token"


async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcloud_config_flow: MagicMock,
) -> None:
    """Test reauth flow with invalid authentication and recovery."""
    mock_config_entry.add_to_hass(hass)
    mock_hcloud_config_flow.load_balancers.get_all.side_effect = APIException(
        code=401, message="Unauthorized", details={}
    )

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_TOKEN: "bad-new-token"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Recover from error
    mock_hcloud_config_flow.load_balancers.get_all.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_TOKEN: "new-api-token"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_TOKEN] == "new-api-token"


async def test_reauth_flow_unknown_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcloud_config_flow: MagicMock,
) -> None:
    """Test reauth flow with unknown error and recovery."""
    mock_config_entry.add_to_hass(hass)
    mock_hcloud_config_flow.load_balancers.get_all.side_effect = RuntimeError(
        "Unexpected"
    )

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_TOKEN: "new-token"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    # Recover from error
    mock_hcloud_config_flow.load_balancers.get_all.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_TOKEN: "new-api-token"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_TOKEN] == "new-api-token"
