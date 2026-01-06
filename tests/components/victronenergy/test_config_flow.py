"""Test the Victron Energy config flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.victronenergy.config_flow import (
    CannotConnect,
    InvalidAuth,
)
from homeassistant.components.victronenergy.const import DOMAIN, CONF_BROKER
from homeassistant.const import CONF_PASSWORD
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


async def test_form_user_success_unsecure_mqtt(hass: HomeAssistant) -> None:
    """Test successful user flow with unsecure MQTT connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.victronenergy.config_flow.validate_input",
            return_value={"title": "GX device (test_device)"},
        ),
        patch(
            "homeassistant.components.victronenergy.config_flow._test_basic_mqtt_connection",
            return_value=True,
        ),
        patch(
            "homeassistant.components.victronenergy.config_flow._detect_discovery_topics",
            return_value="test_device",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BROKER: "192.168.1.100"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "GX device (test_device)"
    assert result["data"] == {
        CONF_BROKER: "192.168.1.100",
        "port": 1883,
    }


async def test_form_password_step(hass: HomeAssistant) -> None:
    """Test password step when unsecure MQTT fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.victronenergy.config_flow.validate_input",
            return_value={"title": "GX device"},
        ),
        patch(
            "homeassistant.components.victronenergy.config_flow._test_basic_mqtt_connection",
            return_value=False,  # Unsecure connection fails
        ),
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

    with (
        patch(
            "homeassistant.components.victronenergy.config_flow.validate_input",
            return_value={"title": "GX device"},
        ),
        patch(
            "homeassistant.components.victronenergy.config_flow._test_basic_mqtt_connection",
            return_value=False,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BROKER: "192.168.1.100"},
        )

    # Test password step
    with (
        patch(
            "homeassistant.components.victronenergy.config_flow._generate_ha_device_id",
            return_value="test_device_id",
        ),
        patch(
            "homeassistant.components.victronenergy.config_flow._generate_victron_token",
            return_value="test_token",
        ),
        patch(
            "homeassistant.components.victronenergy.config_flow._test_secure_mqtt_connection",
            return_value=True,
        ),
        patch(
            "homeassistant.components.victronenergy.config_flow._detect_discovery_topics",
            return_value="test_device",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "test-password"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "GX device (test_device)"
    assert result["data"]["broker"] == "192.168.1.100"
    assert result["data"]["port"] == 8883
    assert "token" in result["data"]


async def test_form_password_invalid_auth(hass: HomeAssistant) -> None:
    """Test password step with invalid authentication."""
    # Get to password step
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.victronenergy.config_flow.validate_input",
            return_value={"title": "GX device"},
        ),
        patch(
            "homeassistant.components.victronenergy.config_flow._test_basic_mqtt_connection",
            return_value=False,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BROKER: "192.168.1.100"},
        )

    # Test invalid auth in password step
    with patch(
        "homeassistant.components.victronenergy.config_flow._generate_victron_token",
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

    with (
        patch(
            "homeassistant.components.victronenergy.config_flow.validate_input",
            return_value={"title": "GX device"},
        ),
        patch(
            "homeassistant.components.victronenergy.config_flow._test_basic_mqtt_connection",
            return_value=False,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BROKER: "192.168.1.100"},
        )

    # Test connection error in password step
    with patch(
        "homeassistant.components.victronenergy.config_flow._generate_victron_token",
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

    with (
        patch(
            "homeassistant.components.victronenergy.config_flow.validate_input",
            return_value={"title": "GX device"},
        ),
        patch(
            "homeassistant.components.victronenergy.config_flow._test_basic_mqtt_connection",
            return_value=True,
        ),
        patch(
            "homeassistant.components.victronenergy.config_flow._detect_discovery_topics",
            return_value="48e7da868f12",  # Same unique ID
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BROKER: "192.168.1.100"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"