"""Tests for the Gree Infrared config flow."""

from typing import Any

import pytest
from pytest_homeassistant.common import MockConfigEntry, get_schema_suggested_value
from pytest_homeassistant.components.infrared import (
    EMITTER_ENTITY_ID as mock_infrared_emitter_entity_id,
    RECEIVER_ENTITY_ID as mock_infrared_receiver_entity_id,
)
from pytest_homeassistant.components.infrared.common import (
    MockInfraredEmitterEntity,
    MockInfraredReceiverEntity,
)

from homeassistant.components.climate import HVACMode
from homeassistant.components.gree_infrared.const import (
    CONF_HVAC_MODES,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
)
from homeassistant.components.infrared import DATA_COMPONENT
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import entity_registry as er

SECOND_EMITTER_ENTITY_ID = "infrared.second_ir_emitter"
SECOND_RECEIVER_ENTITY_ID = "infrared.second_ir_receiver"


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test successful config flow with default modes (cool + dry)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_INFRARED_EMITTER_ENTITY_ID: mock_infrared_emitter_entity_id,
            CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Gree AC via Test IR emitter"
    assert result["data"] == {
        CONF_INFRARED_EMITTER_ENTITY_ID: mock_infrared_emitter_entity_id,
        CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY],
    }
    assert result["result"].unique_id is None


@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
async def test_user_flow_with_heat_and_receiver(hass: HomeAssistant) -> None:
    """Test config flow with heat mode and optional receiver."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_INFRARED_EMITTER_ENTITY_ID: mock_infrared_emitter_entity_id,
            CONF_INFRARED_RECEIVER_ENTITY_ID: mock_infrared_receiver_entity_id,
            CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.HEAT, HVACMode.DRY],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HVAC_MODES] == [
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.DRY,
    ]
    assert result["data"][CONF_INFRARED_RECEIVER_ENTITY_ID] == (
        mock_infrared_receiver_entity_id
    )


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_user_flow_requires_hvac_mode(hass: HomeAssistant) -> None:
    """Test the flow rejects an empty list of supported modes."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with pytest.raises(InvalidData) as err:
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_INFRARED_EMITTER_ENTITY_ID: mock_infrared_emitter_entity_id,
                CONF_HVAC_MODES: [],
            },
        )

    assert err.value.schema_errors == {CONF_HVAC_MODES: "no_hvac_modes"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_INFRARED_EMITTER_ENTITY_ID: mock_infrared_emitter_entity_id,
            CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the flow aborts when the emitter is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_INFRARED_EMITTER_ENTITY_ID: mock_infrared_emitter_entity_id,
            CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY],
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
async def test_user_flow_receiver_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the flow aborts when the receiver is already configured."""
    mock_config_entry.add_to_hass(hass)
    await hass.data[DATA_COMPONENT].async_add_entities(
        [MockInfraredEmitterEntity("second_ir_emitter", "Second IR emitter")]
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_INFRARED_EMITTER_ENTITY_ID: "infrared.second_ir_emitter",
            CONF_INFRARED_RECEIVER_ENTITY_ID: mock_infrared_receiver_entity_id,
            CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY],
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("init_infrared")
async def test_user_flow_no_emitters(hass: HomeAssistant) -> None:
    """Test the flow aborts when no infrared emitters exist."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_emitters"


@pytest.mark.usefixtures("mock_infrared_receiver_entity")
async def test_user_flow_no_emitters_receiver_only(hass: HomeAssistant) -> None:
    """Test the flow aborts when only a receiver is available, since AC needs an emitter."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_emitters"


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
@pytest.mark.parametrize(
    ("entity_name", "expected_title"),
    [
        pytest.param(None, "Gree AC via Test IR emitter", id="original_name"),
        pytest.param("AC IR emitter", "Gree AC via AC IR emitter", id="custom_name"),
    ],
)
async def test_user_flow_title_from_entity_name(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity_name: str | None,
    expected_title: str,
) -> None:
    """Test config entry title uses the entity name."""
    entity_registry.async_update_entity(
        mock_infrared_emitter_entity_id, name=entity_name
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_INFRARED_EMITTER_ENTITY_ID: mock_infrared_emitter_entity_id,
            CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY],
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title


@pytest.fixture
async def mock_second_infrared_entities(
    hass: HomeAssistant, init_infrared: None
) -> None:
    """Add a second infrared emitter and receiver to choose from."""
    await hass.data[DATA_COMPONENT].async_add_entities(
        [
            MockInfraredEmitterEntity("second_ir_emitter", name="Second IR emitter"),
            MockInfraredReceiverEntity("second_ir_receiver", name="Second IR receiver"),
        ]
    )


@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
async def test_reconfigure_flow_suggests_current_values(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the reconfigure form is pre-filled with the current entry data."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    schema = result["data_schema"].schema
    assert (
        get_schema_suggested_value(schema, CONF_INFRARED_EMITTER_ENTITY_ID)
        == mock_infrared_emitter_entity_id
    )
    assert (
        get_schema_suggested_value(schema, CONF_INFRARED_RECEIVER_ENTITY_ID)
        == mock_infrared_receiver_entity_id
    )
    assert get_schema_suggested_value(schema, CONF_HVAC_MODES) == [
        HVACMode.COOL,
        HVACMode.DRY,
    ]


@pytest.mark.usefixtures("mock_second_infrared_entities")
@pytest.mark.parametrize(
    ("has_receiver", "user_input"),
    [
        pytest.param(
            True,
            {
                CONF_INFRARED_EMITTER_ENTITY_ID: SECOND_EMITTER_ENTITY_ID,
                CONF_INFRARED_RECEIVER_ENTITY_ID: mock_infrared_receiver_entity_id,
                CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY],
            },
            id="change_emitter",
        ),
        pytest.param(
            False,
            {
                CONF_INFRARED_EMITTER_ENTITY_ID: mock_infrared_emitter_entity_id,
                CONF_INFRARED_RECEIVER_ENTITY_ID: mock_infrared_receiver_entity_id,
                CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.HEAT, HVACMode.DRY],
            },
            id="add_receiver_and_mode",
        ),
        pytest.param(
            True,
            {
                CONF_INFRARED_EMITTER_ENTITY_ID: mock_infrared_emitter_entity_id,
                CONF_HVAC_MODES: [HVACMode.FAN_ONLY],
            },
            id="remove_receiver_and_change_modes",
        ),
    ],
)
async def test_reconfigure_flow(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    user_input: dict[str, Any],
) -> None:
    """Test reconfiguring replaces the entry data and reloads the entry."""
    result = await init_integration.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert init_integration.data == user_input
    assert init_integration.title == "Gree AC via Test IR emitter"
    assert init_integration.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity",
    "mock_infrared_receiver_entity",
    "mock_second_infrared_entities",
)
@pytest.mark.parametrize(
    "user_input",
    [
        pytest.param(
            {
                CONF_INFRARED_EMITTER_ENTITY_ID: SECOND_EMITTER_ENTITY_ID,
                CONF_INFRARED_RECEIVER_ENTITY_ID: mock_infrared_receiver_entity_id,
                CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY],
            },
            id="emitter_conflict",
        ),
        pytest.param(
            {
                CONF_INFRARED_EMITTER_ENTITY_ID: mock_infrared_emitter_entity_id,
                CONF_INFRARED_RECEIVER_ENTITY_ID: SECOND_RECEIVER_ENTITY_ID,
                CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY],
            },
            id="receiver_conflict",
        ),
    ],
)
async def test_reconfigure_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    user_input: dict[str, Any],
) -> None:
    """Test reconfigure aborts when another entry uses the chosen IR entity."""
    mock_config_entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_INFRARED_EMITTER_ENTITY_ID: SECOND_EMITTER_ENTITY_ID,
            CONF_INFRARED_RECEIVER_ENTITY_ID: SECOND_RECEIVER_ENTITY_ID,
            CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY],
        },
    ).add_to_hass(hass)
    original_data = dict(mock_config_entry.data)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == original_data


@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
async def test_reconfigure_flow_requires_hvac_mode(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure rejects an empty list of supported modes."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    with pytest.raises(InvalidData) as err:
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_INFRARED_EMITTER_ENTITY_ID: mock_infrared_emitter_entity_id,
                CONF_HVAC_MODES: [],
            },
        )

    assert err.value.schema_errors == {CONF_HVAC_MODES: "no_hvac_modes"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_INFRARED_EMITTER_ENTITY_ID: mock_infrared_emitter_entity_id,
            CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY],
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("mock_infrared_receiver_entity")
async def test_reconfigure_flow_no_emitters(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure aborts when only a receiver exists."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_emitters"
