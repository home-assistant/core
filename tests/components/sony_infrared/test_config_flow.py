"""Tests for the Sony Infrared config flow."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.infrared import EMITTER_ENTITY_ID
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity

from homeassistant.components.infrared import DATA_COMPONENT as INFRARED_DATA_COMPONENT
from homeassistant.components.sony_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
    SonyDeviceType,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

UNREGISTERED_EMITTER_ENTITY_ID = "infrared.unregistered_ir_emitter"


@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_setup_entry")
async def test_user_flow(hass: HomeAssistant) -> None:
    """Test a successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE_TYPE: SonyDeviceType.TV,
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Sony TV via Test IR emitter"
    assert result["data"] == {
        CONF_DEVICE_TYPE: SonyDeviceType.TV,
        CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
    }
    assert result["result"].unique_id is None


@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_setup_entry")
async def test_user_flow_title_uses_entity_registry_name(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the entry title uses a name the user gave the emitter."""
    entity_registry.async_update_entity(EMITTER_ENTITY_ID, name="Living room blaster")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE_TYPE: SonyDeviceType.TV,
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Sony TV via Living room blaster"


@pytest.mark.usefixtures("init_infrared", "mock_setup_entry")
async def test_user_flow_title_falls_back_to_entity_id(hass: HomeAssistant) -> None:
    """Test the entry title uses the entity ID when it is not in the registry."""
    emitter = MockInfraredEmitterEntity("unregistered_ir_emitter", None)
    emitter._attr_unique_id = None
    emitter.entity_id = UNREGISTERED_EMITTER_ENTITY_ID
    await hass.data[INFRARED_DATA_COMPONENT].async_add_entities([emitter])

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE_TYPE: SonyDeviceType.TV,
            CONF_INFRARED_ENTITY_ID: UNREGISTERED_EMITTER_ENTITY_ID,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Sony TV via {UNREGISTERED_EMITTER_ENTITY_ID}"


@pytest.mark.usefixtures("init_infrared")
async def test_user_flow_no_emitters(hass: HomeAssistant) -> None:
    """Test the flow aborts when there are no infrared emitters."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_emitters"


@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_setup_entry")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the flow aborts when the device type and emitter are already set up."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE_TYPE: SonyDeviceType.TV,
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
