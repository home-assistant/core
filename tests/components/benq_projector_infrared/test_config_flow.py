"""Tests for the BenQ Projector Infrared config flow."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.benq_projector_infrared.const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_INFRARED_EMITTER_ENTITY_ID, MOCK_INFRARED_RECEIVER_ENTITY_ID


@pytest.mark.parametrize(
    "user_input",
    [
        pytest.param(
            {CONF_INFRARED_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID},
            id="emitter_only",
        ),
        pytest.param(
            {
                CONF_INFRARED_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID,
                CONF_INFRARED_RECEIVER_ENTITY_ID: MOCK_INFRARED_RECEIVER_ENTITY_ID,
            },
            id="with_receiver",
        ),
    ],
)
@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
async def test_user_flow_success(
    hass: HomeAssistant, user_input: dict[str, str]
) -> None:
    """Test successful user config flow, with and without a receiver."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "BenQ projector"
    assert result["data"] == user_input
    assert result["result"].unique_id is None


@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow aborts when a projector already uses the emitter.

    Adding a receiver does not make it a different projector.
    """
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_INFRARED_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID,
            CONF_INFRARED_RECEIVER_ENTITY_ID: MOCK_INFRARED_RECEIVER_ENTITY_ID,
        },
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
    assert result["reason"] == "no_infrared_emitters"
