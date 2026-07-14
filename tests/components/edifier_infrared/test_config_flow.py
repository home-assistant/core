"""Tests for the Edifier Infrared config flow."""

from infrared_protocols.codes.edifier.models import EdifierCommandSet, EdifierModel
import pytest

from homeassistant.components.edifier_infrared.const import (
    CONF_COMMAND_SET,
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.infrared import EMITTER_ENTITY_ID


@pytest.mark.parametrize(
    ("model", "expected_command_set"),
    [
        (EdifierModel.R1700BT, EdifierCommandSet.R1700BT),
        (EdifierModel.R1280DB, EdifierCommandSet.R1280DB),
        (EdifierModel.R1280T, EdifierCommandSet.R1280T),
        (EdifierModel.S360DB, EdifierCommandSet.S360DB),
        (EdifierModel.RC20G, EdifierCommandSet.RC20G),
        (EdifierModel.S3000PRO, EdifierCommandSet.S3000PRO),
    ],
)
@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_user_flow_success(
    hass: HomeAssistant,
    model: EdifierModel,
    expected_command_set: EdifierCommandSet,
) -> None:
    """Test successful user config flow for each command set."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
            CONF_MODEL: model.value,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Edifier {model.value} via Test IR emitter"
    assert result["data"] == {
        CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        CONF_MODEL: model.value,
        CONF_COMMAND_SET: expected_command_set.value,
    }
    assert (
        result["result"].unique_id
        == f"{expected_command_set.value}_{EMITTER_ENTITY_ID}"
    )


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow aborts when entry is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
            CONF_MODEL: EdifierModel.R1700BT.value,
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
@pytest.mark.parametrize(
    ("entity_name", "expected_title"),
    [
        (None, "Edifier R1700BT via Test IR emitter"),
        ("Living room IR", "Edifier R1700BT via Living room IR"),
    ],
)
async def test_user_flow_title_from_entity_name(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity_name: str | None,
    expected_title: str,
) -> None:
    """Test config entry title uses the entity name."""
    entity_registry.async_update_entity(EMITTER_ENTITY_ID, name=entity_name)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
            CONF_MODEL: EdifierModel.R1700BT.value,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title
