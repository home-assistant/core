"""Tests for the Marantz Infrared config flow."""

import pytest

from homeassistant.components.infrared import (
    DATA_COMPONENT as INFRARED_DATA_COMPONENT,
    DOMAIN as INFRARED_DOMAIN,
)
from homeassistant.components.marantz_infrared.const import (
    CONF_INFRARED_EMITTER_ENTITY_ID,
    CONF_MODEL,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from .conftest import MOCK_INFRARED_ENTITY_ID, MockInfraredEntity

from tests.common import MockConfigEntry


@pytest.fixture
async def setup_infrared(
    hass: HomeAssistant, mock_infrared_entity: MockInfraredEntity
) -> None:
    """Set up the infrared component with a mock entity."""
    assert await async_setup_component(hass, INFRARED_DOMAIN, {})
    await hass.async_block_till_done()

    component = hass.data[INFRARED_DATA_COMPONENT]
    await component.async_add_entities([mock_infrared_entity])


@pytest.mark.usefixtures("setup_infrared")
async def test_user_flow_success(
    hass: HomeAssistant,
) -> None:
    """Test successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODEL: "pm6006_integrated_amplifier",
            CONF_INFRARED_EMITTER_ENTITY_ID: MOCK_INFRARED_ENTITY_ID,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "PM6006 Integrated Amplifier"
    assert result["data"] == {
        CONF_MODEL: "pm6006_integrated_amplifier",
        CONF_INFRARED_EMITTER_ENTITY_ID: MOCK_INFRARED_ENTITY_ID,
    }
    assert (
        result["result"].unique_id
        == f"pm6006_integrated_amplifier_{MOCK_INFRARED_ENTITY_ID}"
    )


@pytest.mark.usefixtures("setup_infrared")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow aborts when entry is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODEL: "pm6006_integrated_amplifier",
            CONF_INFRARED_EMITTER_ENTITY_ID: MOCK_INFRARED_ENTITY_ID,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_no_emitters(hass: HomeAssistant) -> None:
    """Test user flow aborts when no infrared emitters exist."""
    assert await async_setup_component(hass, INFRARED_DOMAIN, {})
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_emitters"


@pytest.mark.usefixtures("setup_infrared")
@pytest.mark.parametrize(
    ("model", "expected_title"),
    [
        ("generic_amplifier", "Generic Amplifier"),
        ("pm6006_integrated_amplifier", "PM6006 Integrated Amplifier"),
    ],
)
async def test_user_flow_title_from_model(
    hass: HomeAssistant, model: str, expected_title: str
) -> None:
    """Test config entry title is the model name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODEL: model,
            CONF_INFRARED_EMITTER_ENTITY_ID: MOCK_INFRARED_ENTITY_ID,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title
