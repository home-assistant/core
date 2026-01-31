"""Configuration flow tests for the Lyngdorf integration."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components import ssdp
from homeassistant.components.lyngdorf.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.usefixtures("mock_find_receiver_model", "mock_get_mac_address")
async def test_user_flow_no_devices(hass: HomeAssistant) -> None:
    """Test user flow when no devices are discovered."""
    with patch.object(ssdp, "async_get_discovery_info_by_st", return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


@pytest.mark.usefixtures("mock_find_receiver_model", "mock_get_mac_address")
async def test_manual_flow(hass: HomeAssistant) -> None:
    """Test the manual configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    # Should redirect to manual since no discoveries
    with patch.object(ssdp, "async_get_discovery_info_by_st", return_value=[]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=None,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    # Configure with manual input
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "My Lyngdorf",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    config_entry = result["result"]
    assert config_entry.unique_id == "mp-60:192.168.1.100"
    assert config_entry.data[CONF_HOST] == "192.168.1.100"
    assert config_entry.title == "My Lyngdorf"


@pytest.mark.usefixtures("mock_find_receiver_model", "mock_get_mac_address")
async def test_manual_flow_already_configured(hass: HomeAssistant) -> None:
    """Test manual flow when device is already configured."""
    # Create an existing entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="mp-60:192.168.1.100",
        data={CONF_HOST: "192.168.1.50", CONF_MAC: None},
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with patch.object(ssdp, "async_get_discovery_info_by_st", return_value=[]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=None,
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "My Lyngdorf",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_manual_flow_unsupported_model(hass: HomeAssistant) -> None:
    """Test manual flow when model is not supported."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with patch.object(ssdp, "async_get_discovery_info_by_st", return_value=[]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=None,
        )

    # Mock async_find_receiver_model to return None (unsupported model)
    with patch(
        "homeassistant.components.lyngdorf.config_flow.async_find_receiver_model",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.1.100",
                CONF_NAME: "My Lyngdorf",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unsupported_model"}


@pytest.mark.usefixtures("mock_get_mac_address")
async def test_manual_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test manual flow when cannot connect to receiver."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with patch.object(ssdp, "async_get_discovery_info_by_st", return_value=[]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=None,
        )

    # Mock async_find_receiver_model to raise an exception
    with patch(
        "homeassistant.components.lyngdorf.config_flow.async_find_receiver_model",
        side_effect=ConnectionError("Unable to connect"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.1.100",
                CONF_NAME: "My Lyngdorf",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.usefixtures("mock_get_mac_address")
async def test_manual_flow_timeout(hass: HomeAssistant) -> None:
    """Test manual flow when connection times out."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with patch.object(ssdp, "async_get_discovery_info_by_st", return_value=[]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=None,
        )

    # Mock async_find_receiver_model to raise timeout
    with patch(
        "homeassistant.components.lyngdorf.config_flow.async_find_receiver_model",
        side_effect=TimeoutError("Connection timeout"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.1.100",
                CONF_NAME: "My Lyngdorf",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "timeout_connect"}


async def test_manual_flow_unknown_error(hass: HomeAssistant) -> None:
    """Test manual flow with unknown exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with patch.object(ssdp, "async_get_discovery_info_by_st", return_value=[]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=None,
        )

    # Mock async_find_receiver_model to raise an unexpected exception
    with patch(
        "homeassistant.components.lyngdorf.config_flow.async_find_receiver_model",
        side_effect=Exception("Unexpected error"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.1.100",
                CONF_NAME: "My Lyngdorf",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
