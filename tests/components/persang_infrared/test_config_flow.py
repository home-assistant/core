"""Tests for the Persang Infrared config flow."""

import pytest

from homeassistant.components.persang_infrared.const import (
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_INFRARED_EMITTER_ENTITY_ID

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_EMITTER_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Persang speaker"
    assert result["data"] == {
        CONF_INFRARED_EMITTER_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID
    }
    assert result["result"].unique_id == MOCK_INFRARED_EMITTER_ENTITY_ID


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow aborts when the transmitter is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_EMITTER_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("init_infrared")
async def test_user_flow_no_emitters(hass: HomeAssistant) -> None:
    """Test user flow aborts when no infrared emitters exist."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_emitters"
