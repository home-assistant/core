"""Test Duosida EV config flow."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.duosida_ev.const import (
    CONF_DEVICE_ID,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_DISCOVERED_CHARGER  # noqa: F401


async def test_user_step_no_discovery(
    hass: HomeAssistant,
    mock_duosida_charger: Any,
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
        "homeassistant.components.duosida_ev.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 9988,
                CONF_DEVICE_ID: "03123456789012345678",
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Duosida 192.168.1.100"
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 9988,
        CONF_DEVICE_ID: "03123456789012345678",
    }


async def test_manual_step_connection_error(
    hass: HomeAssistant,
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
        "homeassistant.components.duosida_ev.config_flow.DuosidaCharger"
    ) as mock_charger_class:
        mock_charger = mock_charger_class.return_value
        mock_charger.connect.return_value = False

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 9988,
                CONF_DEVICE_ID: "03123456789012345678",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_discovery_step_chargers_found(
    hass: HomeAssistant,
    mock_discover_chargers: Any,
    mock_duosida_charger: Any,
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
        "homeassistant.components.duosida_ev.async_setup_entry",
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
) -> None:
    """Test discovery step when no chargers are found."""
    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Choose discovery with no chargers found
    with patch(
        "homeassistant.components.duosida_ev.config_flow.discover_chargers",
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
        },
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_manual_defaults(
    hass: HomeAssistant,
    mock_duosida_charger: Any,
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

    # Configure without specifying port (should use default)
    with patch(
        "homeassistant.components.duosida_ev.async_setup_entry",
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
    # Verify default was used
    assert result["data"][CONF_PORT] == DEFAULT_PORT


async def test_manual_step_auto_detect_device_id(
    hass: HomeAssistant,
) -> None:
    """Test manual configuration auto-detects device_id when not provided."""
    from unittest.mock import MagicMock

    from .conftest import MockChargerStatus, MOCK_CHARGER_STATUS

    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Go to manual step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"discovery": False},
    )

    # Configure without device_id - should auto-detect
    with (
        patch(
            "homeassistant.components.duosida_ev.config_flow.DuosidaCharger"
        ) as mock_charger_class,
        patch(
            "homeassistant.components.duosida_ev.async_setup_entry",
            return_value=True,
        ),
    ):
        mock_charger = MagicMock()
        mock_charger.connect.return_value = True
        mock_charger.get_status.return_value = MockChargerStatus(MOCK_CHARGER_STATUS)
        mock_charger.device_id = "03999888777666555444"
        mock_charger.disconnect.return_value = None
        mock_charger_class.return_value = mock_charger

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 9988,
                # No device_id - should be auto-detected
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_ID] == "03999888777666555444"


async def test_manual_step_auto_detect_device_id_fails(
    hass: HomeAssistant,
) -> None:
    """Test manual configuration fails when auto-detect fails."""
    from unittest.mock import MagicMock

    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Go to manual step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"discovery": False},
    )

    # Configure without device_id but get_status fails
    with patch(
        "homeassistant.components.duosida_ev.config_flow.DuosidaCharger"
    ) as mock_charger_class:
        mock_charger = MagicMock()
        mock_charger.connect.return_value = True
        mock_charger.get_status.return_value = None  # Status fetch fails
        mock_charger.disconnect.return_value = None
        mock_charger_class.return_value = mock_charger

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 9988,
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_manual_step_exception(
    hass: HomeAssistant,
) -> None:
    """Test manual configuration handles exception."""
    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Go to manual step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"discovery": False},
    )

    # Configuration raises an exception
    with patch(
        "homeassistant.components.duosida_ev.config_flow.DuosidaCharger"
    ) as mock_charger_class:
        mock_charger_class.side_effect = Exception("Network error")

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 9988,
                CONF_DEVICE_ID: "03123456789012345678",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
