"""Test the Briiv config flow."""

from unittest.mock import patch

from pybriiv import BriivError

from homeassistant import config_entries
from homeassistant.components.briiv.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_discovery_flow(hass: HomeAssistant) -> None:
    """Test we can discover devices properly."""

    # Mock discovery to return a single device
    discovered_devices = [
        {
            "serial_number": "TEST123",
            "host": "192.168.1.100",
            "is_pro": False,
        }
    ]

    with patch("pybriiv.BriivAPI.discover", return_value=discovered_devices):
        # Start the flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        # Select the discovered device
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"action": "Briiv (TEST123)"}
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Briiv (TEST123)"
        assert result["data"] == {
            "host": "192.168.1.100",
            "port": 3334,
            "serial_number": "TEST123",
        }


async def test_discovery_error(hass: HomeAssistant) -> None:
    """Test we handle discovery errors properly."""

    with patch("pybriiv.BriivAPI.discover", side_effect=BriivError("Discovery failed")):
        # Start the flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "discovery_error"


async def test_manual_flow(hass: HomeAssistant) -> None:
    """Test manually configuring a device."""

    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Configure without discovering devices, using manual option
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"action": "Manual Configuration"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual"

    # Submit manual configuration
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.200", "serial_number": "MANUAL123"}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Briiv MANUAL123"
    assert result["data"] == {
        CONF_HOST: "192.168.1.200",
        CONF_PORT: 3334,
        "serial_number": "MANUAL123",
    }
