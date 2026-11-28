"""Test the Ceiling Fan Infrared config flow."""

import pytest
from pytest_homeassistant.common import MockConfigEntry, get_schema_suggested_value
from pytest_homeassistant.components.infrared import EMITTER_ENTITY_ID
from pytest_homeassistant.components.infrared.common import (
    MockInfraredEmitterEntity,
    init_infrared_fixture_helper,
)

from homeassistant.components.ceiling_fan_infrared.const import (
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
)
from homeassistant.components.infrared import DATA_COMPONENT
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

SECOND_EMITTER_ENTITY_ID = "infrared.second_ir_emitter"


@pytest.fixture
async def mock_second_infrared_emitter(
    hass: HomeAssistant, init_infrared: None
) -> None:
    """Add a second infrared emitter to choose from."""
    await hass.data[DATA_COMPONENT].async_add_entities(
        [MockInfraredEmitterEntity("second_ir_emitter", name="Second IR emitter")]
    )


@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_setup_entry")
async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the full user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Ceiling fan via Test IR emitter"
    assert result["data"] == {CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID}
    assert result["result"].unique_id is None


@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_setup_entry")
async def test_user_flow_missing_emitter(hass: HomeAssistant) -> None:
    """Test the user flow requires an emitter."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})


class _UnregisteredEmitter(MockInfraredEmitterEntity):
    """Emitter without a unique ID, so it has no entity registry entry."""

    def __init__(self) -> None:
        """Initialize the emitter."""
        super().__init__("unregistered")
        self._attr_unique_id = None


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_with_an_unregistered_emitter(hass: HomeAssistant) -> None:
    """Test the entry title falls back to the entity ID when the emitter is unregistered."""
    await init_infrared_fixture_helper(hass)
    emitter = _UnregisteredEmitter()
    await hass.data[DATA_COMPONENT].async_add_entities([emitter])
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: emitter.entity_id},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Ceiling fan via {emitter.entity_id}"
    assert result["data"] == {CONF_INFRARED_ENTITY_ID: emitter.entity_id}


@pytest.mark.usefixtures("init_infrared")
async def test_user_flow_no_emitters(hass: HomeAssistant) -> None:
    """Test the user flow aborts when there are no infrared emitters."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_emitters"


@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_setup_entry")
async def test_user_flow_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the user flow aborts when the emitter is already configured."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_reconfigure_flow_suggests_current_emitter(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the reconfigure form is pre-filled with the current emitter."""
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert (
        get_schema_suggested_value(
            result["data_schema"].schema, CONF_INFRARED_ENTITY_ID
        )
        == EMITTER_ENTITY_ID
    )


@pytest.mark.usefixtures(
    "mock_setup_entry", "mock_infrared_emitter_entity", "mock_second_infrared_emitter"
)
@pytest.mark.parametrize(
    "emitter_entity_id",
    [SECOND_EMITTER_ENTITY_ID, EMITTER_ENTITY_ID],
    ids=["change_emitter", "same_emitter"],
)
async def test_reconfigure_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    emitter_entity_id: str,
) -> None:
    """Test reconfiguring updates the emitter and reloads the entry."""
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: emitter_entity_id},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == {CONF_INFRARED_ENTITY_ID: emitter_entity_id}


@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_second_infrared_emitter")
async def test_reconfigure_flow_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test reconfigure aborts when another entry uses the chosen emitter."""
    config_entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN,
        title="Ceiling fan via Second IR emitter",
        data={CONF_INFRARED_ENTITY_ID: SECOND_EMITTER_ENTITY_ID},
    ).add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: SECOND_EMITTER_ENTITY_ID},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data == {CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID}


@pytest.mark.usefixtures("init_infrared")
async def test_reconfigure_flow_no_emitters(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test reconfigure aborts when there are no infrared emitters."""
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_emitters"
