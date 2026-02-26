"""Tests for Eufy RoboVac cloud onboarding config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.components.eufy_robovac.cloud_api import (
    CloudDiscoveredRoboVac,
    EufyRoboVacCloudApiError,
    EufyRoboVacCloudApiInvalidAuth,
)
from homeassistant.components.eufy_robovac.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

ACCOUNT_INPUT = {
    "username": "user@example.com",
    "password": "supersecret",
}

DISCOVERED_DEVICE = CloudDiscoveredRoboVac(
    device_id="abc123",
    model="T2253",
    name="Hall Vacuum",
    local_key="abcdefghijklmnop",
    host="192.168.1.50",
    mac="AA:BB:CC:DD:EE:FF",
    description="RoboVac",
    protocol_version="3.3",
)


async def test_cloud_flow_unsupported_models_filtered(hass) -> None:
    """Flow should reject discovery payloads that have no supported models."""
    unsupported = CloudDiscoveredRoboVac(
        device_id="unsupported1",
        model="T9999",
        name="Unsupported Vacuum",
        local_key="abcdefghijklmnop",
        host="192.168.1.88",
        mac="AA:BB:CC:DD:EE:11",
        description="Unsupported",
        protocol_version="3.3",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.eufy_robovac.config_flow.EufyRoboVacCloudApi.async_list_robovacs",
        AsyncMock(return_value=[unsupported]),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=ACCOUNT_INPUT,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "no_devices"}


async def test_cloud_flow_success(hass) -> None:
    """Cloud onboarding flow should discover, select and create entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.eufy_robovac.config_flow.EufyRoboVacCloudApi.async_list_robovacs",
        AsyncMock(return_value=[DISCOVERED_DEVICE]),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=ACCOUNT_INPUT,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "select_device"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={"selected_device_id": DISCOVERED_DEVICE.device_id},
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "device"

    with patch(
        "homeassistant.components.eufy_robovac.config_flow._async_validate_local_connection",
        AsyncMock(return_value=None),
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            user_input={
                "host": "192.168.1.50",
                "protocol_version": "3.3",
            },
        )

    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert result4["title"] == "Hall Vacuum"
    assert result4["data"]["id"] == "abc123"
    assert result4["data"]["model"] == "T2253"
    assert result4["data"]["local_key"] == "abcdefghijklmnop"
    assert result4["data"]["host"] == "192.168.1.50"
    assert result4["data"]["protocol_version"] == "3.3"


async def test_cloud_flow_recovers_from_missing_selected_device(hass) -> None:
    """Flow should recover if selected device is no longer present in memory."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.eufy_robovac.config_flow.EufyRoboVacCloudApi.async_list_robovacs",
        AsyncMock(return_value=[DISCOVERED_DEVICE]),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=ACCOUNT_INPUT,
        )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "select_device"

    flow_handler = hass.config_entries.flow._progress[result2["flow_id"]]  # noqa: SLF001
    flow_handler._selected_device_id = DISCOVERED_DEVICE.device_id  # noqa: SLF001
    flow_handler._cloud_devices = {}  # noqa: SLF001

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input=None,
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "user"
    assert result3["errors"] == {"base": "no_devices"}


async def test_cloud_flow_invalid_auth(hass) -> None:
    """Invalid cloud credentials should return to login with invalid_auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.eufy_robovac.config_flow.EufyRoboVacCloudApi.async_list_robovacs",
        AsyncMock(side_effect=EufyRoboVacCloudApiInvalidAuth),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=ACCOUNT_INPUT,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_cloud_flow_cannot_connect(hass) -> None:
    """Cloud API connectivity failures should return cannot_connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.eufy_robovac.config_flow.EufyRoboVacCloudApi.async_list_robovacs",
        AsyncMock(side_effect=EufyRoboVacCloudApiError),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=ACCOUNT_INPUT,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_cloud_flow_aborts_on_duplicate_unique_id(hass) -> None:
    """Flow should abort if selected cloud device is already configured."""
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
        "homeassistant.components.eufy_robovac.config_flow.EufyRoboVacCloudApi.async_list_robovacs",
        AsyncMock(return_value=[DISCOVERED_DEVICE]),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=ACCOUNT_INPUT,
        )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "select_device"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={"selected_device_id": DISCOVERED_DEVICE.device_id},
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "device"

    with patch(
        "homeassistant.components.eufy_robovac.config_flow._async_validate_local_connection",
        AsyncMock(return_value=None),
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            user_input={
                "host": "192.168.1.200",
                "protocol_version": "3.3",
            },
        )

    assert result4["type"] is FlowResultType.ABORT
    assert result4["reason"] == "already_configured"
