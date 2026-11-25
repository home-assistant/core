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

    # The flow recovers once a valid emitter is selected.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == _expected_data(entity_registry, EMITTER_ENTITY_ID)


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
async def test_user_flow_already_configured_after_a_rename_while_unloaded(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a stale entity ID does not allow a second entry for the same emitter."""
    registry_entry = entity_registry.async_get(EMITTER_ENTITY_ID)
    assert registry_entry is not None
    MockConfigEntry(
        domain=DOMAIN,
        title="Ceiling fan via Test IR emitter",
        data={
            CONF_INFRARED_ENTITY_ID: "infrared.stale_emitter_id",
            CONF_INFRARED_ENTITY_UUID: registry_entry.id,
        },
    ).add_to_hass(hass)

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
async def test_user_flow_aborts_when_a_stale_entity_id_hides_the_same_emitter(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a stale saved entity ID does not hide an entry that uses the emitter."""
    registry_entry = entity_registry.async_get(EMITTER_ENTITY_ID)
    assert registry_entry is not None
    MockConfigEntry(
        domain=DOMAIN,
        title="Ceiling fan via stale entity ID",
        data={
            CONF_INFRARED_ENTITY_ID: "infrared.stale_emitter_id",
            CONF_INFRARED_ENTITY_UUID: registry_entry.id,
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_allows_a_different_emitter_that_reuses_an_entity_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a reused entity ID is not mistaken for the configured emitter.

    Emitter A is renamed while the fan entry is unloaded, then emitter B takes
    A's old entity ID. The entry's stale ID must not block configuring B.
    """
    await init_infrared_fixture_helper(hass)
    first = MockInfraredEmitterEntity("first_ir_emitter", "Shared name")
    await hass.data[DATA_COMPONENT].async_add_entities([first])
    await hass.async_block_till_done()

    stale_entity_id = first.entity_id
    first_entry = entity_registry.async_get(stale_entity_id)
    assert first_entry is not None
    entity_registry.async_update_entity(
        stale_entity_id, new_entity_id="infrared.renamed_first_emitter"
    )
    await hass.async_block_till_done()

    second = MockInfraredEmitterEntity("second_ir_emitter", "Shared name")
    await hass.data[DATA_COMPONENT].async_add_entities([second])
    await hass.async_block_till_done()
    assert second.entity_id == stale_entity_id
    second_entry = entity_registry.async_get(stale_entity_id)
    assert second_entry is not None

    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_INFRARED_ENTITY_ID: stale_entity_id,
            CONF_INFRARED_ENTITY_UUID: first_entry.id,
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: stale_entity_id},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_INFRARED_ENTITY_ID: stale_entity_id,
        CONF_INFRARED_ENTITY_UUID: second_entry.id,
    }
