"""Tests for Eufy RoboVac config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.components.eufy_robovac.const import DOMAIN
from homeassistant.components.eufy_robovac.local_api import EufyRoboVacLocalApiError
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


USER_INPUT = {
    "name": "Hall Vacuum",
    "model": "T2253",
    "host": " 192.168.1.50 ",
    "id": " abc123 ",
    "local_key": " abcdefghijklmnop ",
    "protocol_version": "3.3",
}


async def test_user_flow_success(hass) -> None:
    """User flow should create an entry after successful local validation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.eufy_robovac.config_flow.EufyRoboVacLocalApi.async_get_dps",
        AsyncMock(return_value={"15": "standby"}),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=USER_INPUT,
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Hall Vacuum"
    assert result2["data"]["host"] == "192.168.1.50"
    assert result2["data"]["id"] == "abc123"
    assert result2["data"]["local_key"] == "abcdefghijklmnop"
    assert result2["data"]["protocol_version"] == "3.3"


async def test_user_flow_cannot_connect(hass) -> None:
    """Connection failures should return to user form with cannot_connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.eufy_robovac.config_flow.EufyRoboVacLocalApi.async_get_dps",
        AsyncMock(side_effect=EufyRoboVacLocalApiError("boom")),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=USER_INPUT,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_flow_aborts_on_duplicate_unique_id(hass) -> None:
    """Flow should abort if the same device is already configured."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="abc123",
        data={
            "name": "Existing Vacuum",
            "model": "T2253",
            "host": "192.168.1.200",
            "id": "abc123",
            "local_key": "abcdefghijklmnop",
            "protocol_version": "3.3",
        },
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.eufy_robovac.config_flow.EufyRoboVacLocalApi.async_get_dps",
        AsyncMock(return_value={"15": "standby"}),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=USER_INPUT,
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
