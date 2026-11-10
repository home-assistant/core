"""Tests for the Alpha Bidet Infrared config flow."""

import pytest
from pytest_homeassistant.common import MockConfigEntry, get_schema_suggested_value
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity

from homeassistant.components.alpha_bidet_infrared.const import (
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DOMAIN,
    AlphaBidetModel,
)
from homeassistant.components.infrared import DATA_COMPONENT as INFRARED_DATA_COMPONENT
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_INFRARED_EMITTER_ENTITY_ID

SECOND_EMITTER_ENTITY_ID = "infrared.second_ir_emitter"


@pytest.fixture
async def mock_second_infrared_emitter(
    hass: HomeAssistant, init_infrared: None
) -> None:
    """Add a second infrared emitter to choose from."""
    await hass.data[INFRARED_DATA_COMPONENT].async_add_entities(
        [MockInfraredEmitterEntity("second_ir_emitter", name="Second IR emitter")]
    )


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
        user_input={
            CONF_INFRARED_EMITTER_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID,
            CONF_MODEL: AlphaBidetModel.JX2.value,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Alpha Bidet JX2"
    assert result["data"] == {
        CONF_INFRARED_EMITTER_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID,
        CONF_MODEL: AlphaBidetModel.JX2.value,
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
        user_input={
            CONF_INFRARED_EMITTER_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID,
            CONF_MODEL: AlphaBidetModel.JX2.value,
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
    assert result["reason"] == "no_emitters"


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_reconfigure_flow_suggests_current_emitter(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the reconfigure form is pre-filled with the current emitter."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert (
        get_schema_suggested_value(
            result["data_schema"].schema, CONF_INFRARED_EMITTER_ENTITY_ID
        )
        == MOCK_INFRARED_EMITTER_ENTITY_ID
    )


@pytest.mark.usefixtures("mock_second_infrared_emitter")
@pytest.mark.parametrize(
    "emitter_entity_id",
    [
        pytest.param(SECOND_EMITTER_ENTITY_ID, id="change_emitter"),
        pytest.param(MOCK_INFRARED_EMITTER_ENTITY_ID, id="same_emitter"),
    ],
)
async def test_reconfigure_flow(
    hass: HomeAssistant, init_integration: MockConfigEntry, emitter_entity_id: str
) -> None:
    """Test reconfiguring updates the emitter and unique ID and reloads the entry."""
    result = await init_integration.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_EMITTER_ENTITY_ID: emitter_entity_id},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert init_integration.data == {
        CONF_INFRARED_EMITTER_ENTITY_ID: emitter_entity_id,
        CONF_MODEL: AlphaBidetModel.JX2.value,
    }
    assert init_integration.unique_id == emitter_entity_id
    assert init_integration.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_second_infrared_emitter")
async def test_reconfigure_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure aborts when another entry uses the chosen emitter."""
    mock_config_entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_INFRARED_EMITTER_ENTITY_ID: SECOND_EMITTER_ENTITY_ID,
            CONF_MODEL: AlphaBidetModel.JX2.value,
        },
        unique_id=SECOND_EMITTER_ENTITY_ID,
    ).add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_EMITTER_ENTITY_ID: SECOND_EMITTER_ENTITY_ID},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert (
        mock_config_entry.data[CONF_INFRARED_EMITTER_ENTITY_ID]
        == MOCK_INFRARED_EMITTER_ENTITY_ID
    )
    assert mock_config_entry.unique_id == MOCK_INFRARED_EMITTER_ENTITY_ID


@pytest.mark.usefixtures("init_infrared")
async def test_reconfigure_flow_no_emitters(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure aborts when no infrared emitters exist."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_emitters"
