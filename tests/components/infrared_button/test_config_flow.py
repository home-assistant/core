"""Test the Infrared button config flow."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.components.infrared import (
    EMITTER_ENTITY_ID,
    RECEIVER_ENTITY_ID,
)
from pytest_homeassistant.components.infrared.common import MockInfraredReceiverEntity

from homeassistant.components.infrared import InfraredReceivedSignal
from homeassistant.components.infrared_button.config_flow import LEARN_TIMEOUT
from homeassistant.components.infrared_button.const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    CONF_MODULATION,
    CONF_TIMINGS,
    DOMAIN,
    SUBENTRY_TYPE_COMMAND,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TIMINGS


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_user_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test creating a device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "Living room TV", CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living room TV"
    assert result["data"] == {CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("init_infrared")
async def test_user_flow_no_emitters(hass: HomeAssistant) -> None:
    """Test the flow aborts without emitters."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_emitters"


@pytest.mark.parametrize("modulation", [None, 36000])
@pytest.mark.usefixtures("mock_setup_entry")
async def test_command_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    modulation: int | None,
) -> None:
    """Test learning a command and naming it."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_COMMAND),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_INFRARED_RECEIVER_ENTITY_ID: RECEIVER_ENTITY_ID}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "wait_for_signal"

    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=TIMINGS, modulation=modulation)
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "name"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_NAME: "Power"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Power"
    assert result["data"] == {
        CONF_TIMINGS: TIMINGS,
        CONF_MODULATION: modulation or 38000,
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_command_flow_no_signal(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the flow asks again when no signal comes in, and then recovers."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_COMMAND),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_INFRARED_RECEIVER_ENTITY_ID: RECEIVER_ENTITY_ID}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    freezer.tick(LEARN_TIMEOUT + 1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_signal"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_INFRARED_RECEIVER_ENTITY_ID: RECEIVER_ENTITY_ID}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=TIMINGS)
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "name"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_NAME: "Power"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry", "init_infrared")
async def test_command_flow_no_receivers(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the command flow aborts without receivers."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_COMMAND),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_receivers"
