"""Tests for the Fujitsu Infrared config flow."""

import pytest

from homeassistant.components.climate import HVACMode
from homeassistant.components.fujitsu_infrared.const import (
    CONF_HVAC_MODES,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
    PROTOCOL_STANDARD,
)
from homeassistant.components.infrared import DATA_COMPONENT
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PROTOCOL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.infrared import (
    EMITTER_ENTITY_ID as mock_infrared_emitter_entity_id,
    RECEIVER_ENTITY_ID as mock_infrared_receiver_entity_id,
)
from tests.components.infrared.common import MockInfraredEmitterEntity


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
    assert result["title"] == "Fujitsu AC via Test IR emitter"
    assert result["data"] == {
        CONF_INFRARED_EMITTER_ENTITY_ID: mock_infrared_emitter_entity_id,
        CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY],
        CONF_PROTOCOL: PROTOCOL_STANDARD,
    }
    assert result["result"].unique_id is None


@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
async def test_user_flow_with_heat_cool_and_receiver(hass: HomeAssistant) -> None:
    """Test config flow with the heat/cool mode and the optional receiver."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_INFRARED_EMITTER_ENTITY_ID: mock_infrared_emitter_entity_id,
            CONF_INFRARED_RECEIVER_ENTITY_ID: mock_infrared_receiver_entity_id,
            CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.HEAT, HVACMode.HEAT_COOL],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HVAC_MODES] == [
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.HEAT_COOL,
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
    """Test the flow aborts with only a receiver, since the AC needs an emitter."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_emitters"


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
@pytest.mark.parametrize(
    ("entity_name", "expected_title"),
    [
        pytest.param(None, "Fujitsu AC via Test IR emitter", id="original_name"),
        pytest.param("AC IR emitter", "Fujitsu AC via AC IR emitter", id="custom_name"),
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
