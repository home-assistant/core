"""Tests for the Dyson Infrared config flow."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, get_schema_suggested_value
from pytest_homeassistant.components.infrared import EMITTER_ENTITY_ID
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity

from homeassistant.components.dyson_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DOMAIN,
    DysonDeviceType,
)
from homeassistant.components.infrared import DATA_COMPONENT as INFRARED_DATA_COMPONENT
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

SECOND_EMITTER_ENTITY_ID = "infrared.second_ir_emitter"


@pytest.fixture
async def mock_second_infrared_emitter(
    hass: HomeAssistant, init_infrared: None
) -> None:
    """Add a second infrared emitter to choose from."""
    await hass.data[INFRARED_DATA_COMPONENT].async_add_entities(
        [MockInfraredEmitterEntity("second_ir_emitter", "Second IR emitter")]
    )


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


@pytest.mark.usefixtures("mock_second_infrared_emitter")
@pytest.mark.parametrize(
    "emitter_entity_id",
    [
        pytest.param(SECOND_EMITTER_ENTITY_ID, id="change_emitter"),
        pytest.param(EMITTER_ENTITY_ID, id="same_emitter"),
    ],
)
async def test_reconfigure_flow(
    hass: HomeAssistant, init_integration: MockConfigEntry, emitter_entity_id: str
) -> None:
    """Test reconfiguring changes the emitter and keeps the device type."""
    result = await init_integration.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    schema = result["data_schema"].schema
    assert [str(key) for key in schema] == [CONF_INFRARED_EMITTER_ENTITY_ID]
    assert (
        get_schema_suggested_value(schema, CONF_INFRARED_EMITTER_ENTITY_ID)
        == EMITTER_ENTITY_ID
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_EMITTER_ENTITY_ID: emitter_entity_id},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert init_integration.data == {
        CONF_DEVICE_TYPE: DysonDeviceType.FAN,
        CONF_INFRARED_EMITTER_ENTITY_ID: emitter_entity_id,
    }
    assert init_integration.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_second_infrared_emitter")
async def test_reconfigure_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure aborts when the same device type uses the chosen emitter."""
    mock_config_entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE_TYPE: DysonDeviceType.FAN,
            CONF_INFRARED_EMITTER_ENTITY_ID: SECOND_EMITTER_ENTITY_ID,
        },
    ).add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_EMITTER_ENTITY_ID: SECOND_EMITTER_ENTITY_ID},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_INFRARED_EMITTER_ENTITY_ID] == EMITTER_ENTITY_ID


@pytest.mark.usefixtures("init_infrared")
async def test_reconfigure_flow_no_emitters(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure aborts when there are no infrared emitters."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_emitters"
