"""Test Duosida EV config flow."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.duosida_ev.const import (
    CONF_DEVICE_ID,
    CONF_SCAN_INTERVAL,
    CONF_SWITCH_DEBOUNCE,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SWITCH_DEBOUNCE,
    DOMAIN,
)

from .conftest import MOCK_DISCOVERED_CHARGER  # noqa: F401


async def test_user_step_no_discovery(
    hass: HomeAssistant,
    mock_duosida_charger: Any,
    mock_integration: Any,
) -> None:
    """Test user step without choosing discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # User chooses manual configuration (not selecting discovery checkbox)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"discovery": False},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_manual_step_success(
    hass: HomeAssistant,
    mock_duosida_charger: Any,
    mock_integration: Any,
) -> None:
    """Test manual configuration step completes successfully."""
    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Go to manual step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"discovery": False},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual"

    # Complete manual configuration
    with patch(
        "custom_components.duosida_ev.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 9988,
                CONF_DEVICE_ID: "03123456789012345678",
                CONF_SCAN_INTERVAL: 10,
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Duosida 192.168.1.100"
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 9988,
        CONF_DEVICE_ID: "03123456789012345678",
        CONF_SCAN_INTERVAL: 10,
    }


async def test_manual_step_connection_error(
    hass: HomeAssistant,
    mock_integration: Any,
) -> None:
    """Test manual configuration with connection error."""
    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Go to manual step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"discovery": False},
    )

    # Try to configure with a charger that fails to connect
    with patch(
        "custom_components.duosida_ev.config_flow.DuosidaCharger"
    ) as mock_charger_class:
        mock_charger = mock_charger_class.return_value
        mock_charger.connect.return_value = False

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 9988,
                CONF_DEVICE_ID: "03123456789012345678",
                CONF_SCAN_INTERVAL: 10,
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_discovery_step_chargers_found(
    hass: HomeAssistant,
    mock_discover_chargers: Any,
    mock_duosida_charger: Any,
    mock_integration: Any,
) -> None:
    """Test discovery step when chargers are found."""
    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Choose discovery
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"discovery": True},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "discovery"
    assert "device" in result["data_schema"].schema

    # Select discovered charger
    with patch(
        "custom_components.duosida_ev.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "device": "192.168.1.100",
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Duosida 192.168.1.100"
    assert result["data"][CONF_HOST] == "192.168.1.100"
    assert result["data"][CONF_DEVICE_ID] == "03123456789012345678"


async def test_discovery_step_no_chargers_found(
    hass: HomeAssistant,
    mock_duosida_charger: Any,
    mock_integration: Any,
) -> None:
    """Test discovery step when no chargers are found."""
    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Choose discovery with no chargers found
    with patch(
        "custom_components.duosida_ev.config_flow.discover_chargers",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"discovery": True},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices_found"}


async def test_already_configured(
    hass: HomeAssistant,
    mock_config_entry: Any,
    mock_duosida_charger: Any,
    mock_integration: Any,
) -> None:
    """Test we abort if the device is already configured."""
    mock_config_entry.add_to_hass(hass)

    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Go to manual step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"discovery": False},
    )

    # Try to configure the same device
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 9988,
            CONF_DEVICE_ID: "03123456789012345678",  # Same device ID
            CONF_SCAN_INTERVAL: 10,
        },
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_manual_defaults(
    hass: HomeAssistant,
    mock_duosida_charger: Any,
    mock_integration: Any,
) -> None:
    """Test manual configuration uses defaults."""
    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Go to manual step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"discovery": False},
    )

    # Configure without specifying port and scan_interval (should use defaults)
    with patch(
        "custom_components.duosida_ev.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.1.100",
                CONF_DEVICE_ID: "03123456789012345678",
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    # Verify defaults were used
    assert result["data"][CONF_PORT] == DEFAULT_PORT
    assert result["data"][CONF_SCAN_INTERVAL] == DEFAULT_SCAN_INTERVAL


async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: Any,
    mock_integration: Any,
) -> None:
    """Test options flow."""
    mock_config_entry.add_to_hass(hass)

    # Open options flow
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    # Change scan interval to 20 seconds (switch_debounce uses default)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SCAN_INTERVAL: 20,
            CONF_SWITCH_DEBOUNCE: DEFAULT_SWITCH_DEBOUNCE,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_SCAN_INTERVAL: 20,
        CONF_SWITCH_DEBOUNCE: DEFAULT_SWITCH_DEBOUNCE,
    }


async def test_options_flow_custom_value(
    hass: HomeAssistant,
    mock_config_entry: Any,
    mock_integration: Any,
) -> None:
    """Test options flow with existing custom value."""
    # Add entry to hass first
    mock_config_entry.add_to_hass(hass)

    # Set custom scan interval in options
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_SCAN_INTERVAL: 15, CONF_SWITCH_DEBOUNCE: 45}
    )

    # Open options flow
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    # Change to 30 seconds scan interval and 60 seconds debounce
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SCAN_INTERVAL: 30, CONF_SWITCH_DEBOUNCE: 60},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_SCAN_INTERVAL: 30, CONF_SWITCH_DEBOUNCE: 60}
