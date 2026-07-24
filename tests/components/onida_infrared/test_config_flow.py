"""Tests for the Onida Infrared config flow."""

import pytest

from homeassistant.components.climate import HVACMode
from homeassistant.components.onida_infrared.const import (
    CONF_HVAC_MODES,
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.infrared import (
    EMITTER_ENTITY_ID as mock_infrared_emitter_entity_id,
    RECEIVER_ENTITY_ID as mock_infrared_receiver_entity_id,
)


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
            CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id,
            CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Onida AC via Test IR emitter"
    assert result["data"] == {
        CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id,
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
            CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id,
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
                CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id,
                CONF_HVAC_MODES: [],
            },
        )

    assert err.value.schema_errors == {CONF_HVAC_MODES: "no_hvac_modes"}


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
            CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id,
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
    assert result["reason"] == "no_infrared_entities"


@pytest.mark.usefixtures("mock_infrared_receiver_entity")
async def test_user_flow_no_emitters_receiver_only(hass: HomeAssistant) -> None:
    """Test the flow aborts when only a receiver is available, since AC needs an emitter."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_entities"


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
@pytest.mark.parametrize(
    ("entity_name", "expected_title"),
    [
        pytest.param(None, "Onida AC via Test IR emitter", id="original_name"),
        pytest.param("AC IR emitter", "Onida AC via AC IR emitter", id="custom_name"),
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
            CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id,
            CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY],
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title
