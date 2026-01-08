"""Test the Victron Energy config flow."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant import config_entries
from homeassistant.components.victronenergy.config_flow import (
    CannotConnect,
    InvalidAuth,
    InvalidHost,
)
from homeassistant.components.victronenergy.const import CONF_BROKER, CONF_PORT, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form_user_step(hass: HomeAssistant) -> None:
    """Test we get the form for user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_form_user_goes_to_password_step(hass: HomeAssistant) -> None:
    """Test user flow always goes to password step for secure MQTT."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.victronenergy.config_flow.validate_input",
        return_value={"title": "Venus OS Hub", "host": "192.168.1.100"},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BROKER: "192.168.1.100"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "password"
    assert result["errors"] == {}


async def test_form_password_step(hass: HomeAssistant) -> None:
    """Test password step is shown after user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.victronenergy.config_flow.validate_input",
        return_value={"title": "Venus OS Hub", "host": "192.168.1.100"},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BROKER: "192.168.1.100"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "password"
    assert result["errors"] == {}


async def test_form_password_success(hass: HomeAssistant) -> None:
    """Test successful password flow."""
    # Start flow and get to password step
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.victronenergy.config_flow.validate_input",
        return_value={"title": "Venus OS Hub", "host": "192.168.1.100"},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BROKER: "192.168.1.100"},
        )

    # Test password step
    with (
        patch(
            "homeassistant.components.victronenergy.config_flow.validate_secure_mqtt_connection",
            return_value={
                "title": "Venus OS Hub",
                "host": "192.168.1.100",
                "token": "test_token",
                "ha_device_id": "test_device_id",
            },
        ),
        patch(
            "homeassistant.components.victronenergy.config_flow._detect_discovery_topics",
            return_value="test_device",
        ),
        patch("paho.mqtt.client.Client") as mock_mqtt_client,
    ):
        # Configure mock MQTT client to prevent background threads
        mock_client = MagicMock()
        mock_mqtt_client.return_value = mock_client
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "test-password"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "GX device (test_device)"
    assert result["data"] == {
        CONF_BROKER: "192.168.1.100",
        CONF_PORT: 8883,
        CONF_USERNAME: "token/homeassistant/test_device_id",
        CONF_TOKEN: "test_token",
        "ha_device_id": "test_device_id",
    }


async def test_form_password_invalid_auth(hass: HomeAssistant) -> None:
    """Test password step with invalid authentication."""
    # Get to password step
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.victronenergy.config_flow.validate_input",
        return_value={"title": "Venus OS Hub", "host": "192.168.1.100"},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BROKER: "192.168.1.100"},
        )

    # Test invalid auth in password step
    with patch(
        "homeassistant.components.victronenergy.config_flow.validate_secure_mqtt_connection",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "wrong-password"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "password"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_password_cannot_connect(hass: HomeAssistant) -> None:
    """Test password step with connection error."""
    # Get to password step
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.victronenergy.config_flow.validate_input",
        return_value={"title": "Venus OS Hub", "host": "192.168.1.100"},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BROKER: "192.168.1.100"},
        )

    # Test connection error in password step
    with patch(
        "homeassistant.components.victronenergy.config_flow.validate_secure_mqtt_connection",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "test-password"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "password"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_duplicate_entry_prevention(hass: HomeAssistant) -> None:
    """Test that duplicate entries are prevented."""
    # Add existing entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="48e7da868f12",
        data={CONF_BROKER: "192.168.1.100"},
    )
    existing_entry.add_to_hass(hass)

    # Try to add duplicate
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.victronenergy.config_flow.validate_input",
        return_value={"title": "Venus OS Hub", "host": "192.168.1.100"},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BROKER: "192.168.1.100"},
        )

    # Now complete the password step with duplicate unique_id
    with (
        patch(
            "homeassistant.components.victronenergy.config_flow.validate_secure_mqtt_connection",
            return_value={
                "title": "Venus OS Hub",
                "host": "192.168.1.100",
                "token": "test_token",
                "ha_device_id": "test_device_id",
            },
        ),
        patch(
            "homeassistant.components.victronenergy.config_flow._detect_discovery_topics",
            return_value="48e7da868f12",  # Same unique ID as existing entry
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "test-password"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_form_password_no_discovery(hass: HomeAssistant) -> None:
    """Test password step when discovery topics are not found."""
    # Get to password step
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.victronenergy.config_flow.validate_input",
        return_value={"title": "Venus OS Hub", "host": "192.168.1.100"},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BROKER: "192.168.1.100"},
        )

    # Test no discovery topics found
    with (
        patch(
            "homeassistant.components.victronenergy.config_flow.validate_secure_mqtt_connection",
            return_value={
                "title": "Venus OS Hub",
                "host": "192.168.1.100",
                "token": "test_token",
                "ha_device_id": "test_device_id",
            },
        ),
        patch(
            "homeassistant.components.victronenergy.config_flow._detect_discovery_topics",
            return_value=None,  # No discovery topics found
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "test-password"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_discovery"


async def test_form_invalid_host(hass: HomeAssistant) -> None:
    """Test user form with invalid host format."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.victronenergy.config_flow.validate_input",
        side_effect=InvalidHost("Broker is not a valid IP address or hostname"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BROKER: "invalid..host..name"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_host"
