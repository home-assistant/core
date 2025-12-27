"""Tests for Lytiva config flow."""
from __future__ import annotations

import pytest
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.lytiva.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

@pytest.fixture(autouse=True)
def mock_translations():
    """Mock translations."""
    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        return_value={
            "component.lytiva.config.abort.mqtt_not_connected": "The MQTT integration is not set up. Please configure MQTT first.",
            "component.lytiva.config.abort.single_instance_allowed": "Already configured",
        },
    ):
        yield


async def test_form_user(hass: HomeAssistant) -> None:
    """Test we get the form."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_domains", return_value=["mqtt"]
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_form_user_success(hass: HomeAssistant) -> None:
    """Test successful config flow."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_domains", return_value=["mqtt"]
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Lytiva"
    assert result2["data"] == {}


async def test_form_single_instance_allowed(hass: HomeAssistant) -> None:
    """Test that only a single instance is allowed."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_domains", return_value=["mqtt"]
    ):
        # First, set up an entry
        entry = MockConfigEntry(domain=DOMAIN, data={})
        entry.add_to_hass(hass)

        # Try to start another flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_form_mqtt_not_connected(hass: HomeAssistant) -> None:
    """Test that it aborts if mqtt is not connected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "mqtt_not_connected"