"""Tests for the Dyson Infrared config flow."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.infrared import EMITTER_ENTITY_ID

from homeassistant.components.dyson_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DOMAIN,
    DysonDeviceType,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_form_and_create_entry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that the user config flow shows the form and creates an entry."""
    entity_registry.async_update_entity(
        EMITTER_ENTITY_ID, name="My Living Room Emitter"
    )

    with patch(
        "homeassistant.components.dyson_infrared.async_setup_entry",
        return_value=None,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] is None

        user_input = {
            CONF_DEVICE_TYPE: DysonDeviceType.FAN.value,
            CONF_INFRARED_EMITTER_ENTITY_ID: EMITTER_ENTITY_ID,
        }

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input,
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Dyson Fan via My Living Room Emitter"
    assert result2["data"] == user_input
    assert len(mock_setup_entry.mock_calls) == 1
    assert result2["result"].unique_id is None


@pytest.mark.usefixtures("init_infrared")
async def test_abort_no_emitters(hass: HomeAssistant) -> None:
    """Test abort when no infrared emitters are available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_infrared_emitters"


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_abort_if_already_configured(hass: HomeAssistant) -> None:
    """Test abort when the infrared emitter is already configured."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE_TYPE: DysonDeviceType.FAN.value,
            CONF_INFRARED_EMITTER_ENTITY_ID: EMITTER_ENTITY_ID,
        },
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    user_input = {
        CONF_DEVICE_TYPE: DysonDeviceType.FAN.value,
        CONF_INFRARED_EMITTER_ENTITY_ID: EMITTER_ENTITY_ID,
    }

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input,
    )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
