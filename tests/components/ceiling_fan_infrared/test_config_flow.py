"""Test the Ceiling Fan Infrared config flow."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.infrared import (
    EMITTER_ENTITY_ID,
    RECEIVER_ENTITY_ID,
)
from pytest_homeassistant.components.infrared.common import (
    MockInfraredEmitterEntity,
    init_infrared_fixture_helper,
)

from homeassistant.components.ceiling_fan_infrared.const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_ENTITY_UUID,
    DOMAIN,
)
from homeassistant.components.infrared import DATA_COMPONENT
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er


def _expected_data(
    entity_registry: er.EntityRegistry, entity_id: str
) -> dict[str, str]:
    """Return the expected entry data for a registered emitter."""
    registry_entry = entity_registry.async_get(entity_id)
    assert registry_entry is not None
    return {
        CONF_INFRARED_ENTITY_ID: entity_id,
        CONF_INFRARED_ENTITY_UUID: registry_entry.id,
    }


@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_setup_entry")
async def test_user_flow(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the full user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Ceiling fan via Test IR emitter"
    assert result["data"] == _expected_data(entity_registry, EMITTER_ENTITY_ID)


@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_setup_entry")
async def test_user_flow_missing_emitter(hass: HomeAssistant) -> None:
    """Test the user flow shows an error when no emitter is selected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "missing_infrared_entity"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_setup_entry")
async def test_user_flow_stores_the_entity_id_for_a_registry_uuid(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a selection given as a registry UUID is stored as an entity ID."""
    registry_entry = entity_registry.async_get(EMITTER_ENTITY_ID)
    assert registry_entry is not None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: registry_entry.id},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Ceiling fan via Test IR emitter"
    assert result["data"] == _expected_data(entity_registry, EMITTER_ENTITY_ID)


@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity",
    "mock_infrared_receiver_entity",
    "mock_setup_entry",
)
async def test_user_flow_rejects_a_uuid_that_is_not_an_emitter(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a registry UUID that is not a loaded emitter is rejected."""
    receiver_entry = entity_registry.async_get(RECEIVER_ENTITY_ID)
    assert receiver_entry is not None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: receiver_entry.id},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "missing_infrared_entity"}


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
    assert result["reason"] == "no_infrared_entities"


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


@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_setup_entry")
async def test_reconfigure_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the reconfigure flow."""
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == _expected_data(entity_registry, EMITTER_ENTITY_ID)


@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_setup_entry")
async def test_reconfigure_flow_missing_emitter(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the reconfigure flow shows an error when no emitter is selected."""
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "missing_infrared_entity"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == _expected_data(entity_registry, EMITTER_ENTITY_ID)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_emitter_used_by_another_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test the reconfigure flow aborts when another entry uses the emitter."""
    config_entry.add_to_hass(hass)

    other_emitter = MockInfraredEmitterEntity("other_ir_emitter", "Other IR emitter")
    await hass.data[DATA_COMPONENT].async_add_entities([other_emitter])
    await hass.async_block_till_done()

    MockConfigEntry(
        domain=DOMAIN,
        title="Ceiling fan via Other IR emitter",
        data={CONF_INFRARED_ENTITY_ID: "infrared.other_ir_emitter"},
    ).add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: "infrared.other_ir_emitter"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data == {CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID}


@pytest.mark.usefixtures("init_infrared")
async def test_reconfigure_flow_no_emitters(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the reconfigure flow aborts when there are no infrared emitters."""
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_entities"
