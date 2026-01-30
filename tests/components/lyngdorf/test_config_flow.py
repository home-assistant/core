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
    assert config_entry.unique_id == "aa:bb:cc:dd:ee:ff"
    assert config_entry.data[CONF_HOST] == "192.168.1.100"
    assert config_entry.title == "My Lyngdorf"


@pytest.mark.usefixtures("mock_find_receiver_model", "mock_get_mac_address")
async def test_manual_flow_already_configured(hass: HomeAssistant) -> None:
    """Test manual flow when device is already configured."""
    # Create an existing entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
        data={CONF_HOST: "192.168.1.50", CONF_MAC: "aa:bb:cc:dd:ee:ff"},
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
