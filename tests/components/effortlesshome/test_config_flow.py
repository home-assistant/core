"""Tests for the EffortlessHome config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.effortlesshome.config_flow import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_SYSTEM_ID,
    DOMAIN,
    OptionsFlowHandler,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_user_flow_initial(hass: HomeAssistant) -> None:
    """Test initial form is shown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_flow_missing_fields(hass: HomeAssistant) -> None:
    """Test user step validation for missing fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: "", CONF_PASSWORD: ""},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "missing_fields"}


async def test_user_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Test invalid auth returns expected error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    with patch(
        (
            "homeassistant.components.effortlesshome"
            ".config_flow.ConfigFlow._authenticate_firebase"
        ),
        new=AsyncMock(return_value=None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "pw"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_single_system_creates_entry(hass: HomeAssistant) -> None:
    """Test successful user flow with one system."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    with (
        patch(
            (
                "homeassistant.components.effortlesshome"
                ".config_flow.ConfigFlow._authenticate_firebase"
            ),
            new=AsyncMock(
                return_value={
                    "firebase_uid": "uid",
                    "id_token": "token",
                    "refresh_token": "refresh",
                }
            ),
        ),
        patch(
            (
                "homeassistant.components.effortlesshome"
                ".config_flow.ConfigFlow._fetch_system_list"
            ),
            new=AsyncMock(
                return_value=[
                    {
                        "customer_id": 12345,
                        "SystemID": 67890,
                        "ha_url": "http://ha.local",
                    }
                ]
            ),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "pw"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["customer_id"] == "12345"
    assert result["data"]["system_id"] == "67890"


async def test_user_flow_multiple_systems_then_select(hass: HomeAssistant) -> None:
    """Test multi-system path and selection step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    with (
        patch(
            (
                "homeassistant.components.effortlesshome"
                ".config_flow.ConfigFlow._authenticate_firebase"
            ),
            new=AsyncMock(
                return_value={
                    "firebase_uid": "uid",
                    "id_token": "token",
                    "refresh_token": "refresh",
                }
            ),
        ),
        patch(
            (
                "homeassistant.components.effortlesshome"
                ".config_flow.ConfigFlow._fetch_system_list"
            ),
            new=AsyncMock(
                return_value=[
                    {
                        "customer_id": 12345,
                        "SystemID": 67890,
                        "ha_url": "http://ha.local",
                    },
                    {
                        "customer_id": 12345,
                        "SystemID": 67891,
                        "ha_url": "http://other.local",
                    },
                ]
            ),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "pw"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_system"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_SYSTEM_ID: "12345_67891"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["system_id"] == "67891"


async def test_user_flow_no_systems(hass: HomeAssistant) -> None:
    """Test no systems found path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    with (
        patch(
            (
                "homeassistant.components.effortlesshome"
                ".config_flow.ConfigFlow._authenticate_firebase"
            ),
            new=AsyncMock(
                return_value={
                    "firebase_uid": "uid",
                    "id_token": "token",
                    "refresh_token": "refresh",
                }
            ),
        ),
        patch(
            (
                "homeassistant.components.effortlesshome"
                ".config_flow.ConfigFlow._fetch_system_list"
            ),
            new=AsyncMock(return_value=[]),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "pw"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_system_found"}


async def test_user_flow_aborts_for_duplicate(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test duplicate system is not reconfigured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    with (
        patch(
            (
                "homeassistant.components.effortlesshome"
                ".config_flow.ConfigFlow._authenticate_firebase"
            ),
            new=AsyncMock(
                return_value={
                    "firebase_uid": "uid",
                    "id_token": "token",
                    "refresh_token": "refresh",
                }
            ),
        ),
        patch(
            (
                "homeassistant.components.effortlesshome"
                ".config_flow.ConfigFlow._fetch_system_list"
            ),
            new=AsyncMock(
                return_value=[
                    {
                        "customer_id": 12345,
                        "SystemID": 67890,
                        "ha_url": "http://ha.local",
                    }
                ]
            ),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "pw"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_init_form(mock_config_entry: MockConfigEntry) -> None:
    """Test options flow form is shown."""
    result = await OptionsFlowHandler(mock_config_entry).async_step_init()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_options_flow_create_entry(mock_config_entry: MockConfigEntry) -> None:
    """Test options flow saves options."""
    result = await OptionsFlowHandler(mock_config_entry).async_step_init(
        {"debug_mode": True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"debug_mode": True}
