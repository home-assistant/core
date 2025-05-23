"""Test the SensorPush Cloud config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sensorpush_ha import SensorPushCloudAuthError

from homeassistant.components.sensorpush_cloud.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import CONF_DATA, CONF_EMAIL

from tests.common import MockConfigEntry


async def test_user(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    mock_helper: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user initialized flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        CONF_DATA,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test@example.com"
    assert result["data"] == CONF_DATA
    assert result["result"].unique_id == CONF_DATA[CONF_EMAIL]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_already_configured(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we fail on a duplicate entry in the user flow."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("error", "expected"),
    [(SensorPushCloudAuthError, "invalid_auth"), (Exception, "unknown")],
)
async def test_user_error(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    mock_setup_entry: AsyncMock,
    error: Exception,
    expected: str,
) -> None:
    """Test we display errors in the user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    mock_api.async_authorize.side_effect = error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONF_DATA
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected}

    # Show we can recover from errors:
    mock_api.async_authorize.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONF_DATA
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test@example.com"
    assert result["data"] == CONF_DATA
    assert len(mock_setup_entry.mock_calls) == 1
