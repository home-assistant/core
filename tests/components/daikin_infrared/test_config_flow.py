"""Tests for the Daikin Infrared config flow."""

from typing import Any

import pytest
from pytest_homeassistant.common import MockConfigEntry, setup_test_component_platform
from pytest_homeassistant.components.infrared import (
    EMITTER_ENTITY_ID,
    RECEIVER_ENTITY_ID,
)
from pytest_homeassistant.components.infrared.common import (
    MockInfraredEmitterEntity,
    MockInfraredReceiverEntity,
)

from homeassistant.components.daikin_infrared.const import (
    CONF_INFRARED_EMITTER_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
)
from homeassistant.components.infrared import DOMAIN as INFRARED_DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity
from homeassistant.setup import async_setup_component


async def _async_setup_infrared(hass: HomeAssistant, entities: list[Entity]) -> None:
    """Set up the infrared integration with entities from a test platform."""
    setup_test_component_platform(hass, INFRARED_DOMAIN, entities)
    assert await async_setup_component(
        hass, INFRARED_DOMAIN, {INFRARED_DOMAIN: {"platform": "test"}}
    )
    await hass.async_block_till_done()


@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
@pytest.mark.parametrize(
    "user_input",
    [
        pytest.param(
            {CONF_INFRARED_EMITTER_ENTITY_ID: EMITTER_ENTITY_ID}, id="emitter"
        ),
        pytest.param(
            {
                CONF_INFRARED_EMITTER_ENTITY_ID: EMITTER_ENTITY_ID,
                CONF_INFRARED_RECEIVER_ENTITY_ID: RECEIVER_ENTITY_ID,
            },
            id="emitter_and_receiver",
        ),
    ],
)
async def test_user_flow_success(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> None:
    """Test a successful config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Daikin AC via Test IR emitter"
    assert result["data"] == user_input
    assert result["result"].unique_id is None


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
@pytest.mark.parametrize(
    ("entity_name", "expected_title"),
    [
        pytest.param(None, "Daikin AC via Test IR emitter", id="original_name"),
        pytest.param("AC IR emitter", "Daikin AC via AC IR emitter", id="custom_name"),
    ],
)
async def test_user_flow_title_from_entity_name(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity_name: str | None,
    expected_title: str,
) -> None:
    """Test the config entry title uses the emitter's name."""
    entity_registry.async_update_entity(EMITTER_ENTITY_ID, name=entity_name)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_EMITTER_ENTITY_ID: EMITTER_ENTITY_ID},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title


async def test_user_flow_title_without_registry_entry(hass: HomeAssistant) -> None:
    """Test the title falls back to the entity ID for an emitter not in the registry."""
    emitter = MockInfraredEmitterEntity("unused", "Unregistered IR emitter")
    # Without a unique ID the entity is never added to the entity registry
    emitter._attr_unique_id = None
    await _async_setup_infrared(hass, [emitter])

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_EMITTER_ENTITY_ID: emitter.entity_id},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Daikin AC via {emitter.entity_id}"


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
        user_input={CONF_INFRARED_EMITTER_ENTITY_ID: EMITTER_ENTITY_ID},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_receiver_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the flow aborts when the receiver is already configured."""
    mock_config_entry.add_to_hass(hass)
    await _async_setup_infrared(
        hass,
        [
            MockInfraredEmitterEntity("second_ir_emitter", "Second IR emitter"),
            MockInfraredReceiverEntity("test_ir_receiver"),
        ],
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_INFRARED_EMITTER_ENTITY_ID: "infrared.second_ir_emitter",
            CONF_INFRARED_RECEIVER_ENTITY_ID: RECEIVER_ENTITY_ID,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("init_infrared")
async def test_user_flow_no_emitters(hass: HomeAssistant) -> None:
    """Test the flow aborts when no infrared entities exist."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_emitters"


@pytest.mark.usefixtures("mock_infrared_receiver_entity")
async def test_user_flow_no_emitters_receiver_only(hass: HomeAssistant) -> None:
    """Test the flow aborts when only a receiver is available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_emitters"
