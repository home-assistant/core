"""Test the Briiv config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.briiv.api import BriivError
from homeassistant.components.briiv.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture(autouse=True)
def mock_setup_entry():
    """Mock setting up a config entry."""
    with patch(
        "custom_components.briiv.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


async def test_discovery_flow(hass: HomeAssistant) -> None:
    """Test discovery flow works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Mock discovery
    with patch(
        "custom_components.briiv.api.BriivAPI.discover",
        return_value=[
            {
                "host": "192.168.1.100",
                "serial_number": "TEST123",
                "is_pro": True,
            }
        ],
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"action": "Briiv Pro (TEST123)"},
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Briiv Pro (TEST123)"
    assert result2["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 3334,
        CONF_SERIAL_NUMBER: "TEST123",
    }


async def test_manual_flow(hass: HomeAssistant) -> None:
    """Test manual configuration flow works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select manual configuration
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"action": "Manual Configuration"},
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "manual"

    # Submit manual configuration
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_SERIAL_NUMBER: "TEST123",
        },
    )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Briiv TEST123"
    assert result3["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 3334,
        CONF_SERIAL_NUMBER: "TEST123",
    }


async def test_discovery_error(hass: HomeAssistant) -> None:
    """Test discovery error handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.briiv.api.BriivAPI.discover",
        side_effect=BriivError("Test error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"action": "Search Again"},
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "discovery_error"}


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test we handle already configured devices."""
    entry = config_entries.ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Test",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 3334,
            CONF_SERIAL_NUMBER: "TEST123",
        },
        source="test",
        options={},
        unique_id="TEST123",
    )
    hass.config_entries._entries.append(entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    with patch(
        "custom_components.briiv.api.BriivAPI.discover",
        return_value=[
            {
                "host": "192.168.1.100",
                "serial_number": "TEST123",
                "is_pro": False,
            }
        ],
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"action": "Search Again"},
        )

    assert result2["type"] == FlowResultType.FORM
    assert "TEST123" in result2["description_placeholders"]["configured_devices"]
