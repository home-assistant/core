"""Test the Novy Hood config flow."""

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.novy_cooker_hood.commands import COMMAND_LIGHT
from homeassistant.components.novy_cooker_hood.const import (
    CONF_CODE,
    CONF_TRANSMITTER,
    DOMAIN,
)
from homeassistant.components.radio_frequency import DATA_COMPONENT, DOMAIN as RF_DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import TRANSMITTER_ENTITY_ID

from tests.common import MockConfigEntry
from tests.components.radio_frequency.common import MockRadioFrequencyEntity


@pytest.fixture(autouse=True)
def mock_toggle_gap() -> Iterator[None]:
    """Set the toggle gap to 0 so the test step doesn't actually wait."""
    with patch("homeassistant.components.novy_cooker_hood.config_flow._TOGGLE_GAP", 0):
        yield


async def _start_user_flow(hass: HomeAssistant, code: str = "1") -> dict:
    """Start the flow and submit the user step with the given code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert CONF_CODE in result["data_schema"].schema

    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_TRANSMITTER: TRANSMITTER_ENTITY_ID,
            CONF_CODE: code,
        },
    )


async def test_user_flow_test_then_finish(
    hass: HomeAssistant,
    mock_get_codes: MagicMock,
    mock_rf_entity: MockRadioFrequencyEntity,
    entity_registry: er.EntityRegistry,
) -> None:
    """Submitting the user step fires the test, then Finish creates the entry."""
    result = await _start_user_flow(hass, code="3")

    # Test was fired automatically (toggle on, wait, toggle off).
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "test_light"
    mock_get_codes.async_load_command.assert_awaited_with(COMMAND_LIGHT)
    assert len(mock_rf_entity.send_command_calls) == 2

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "finish"}
    )

    entity_entry = entity_registry.async_get(TRANSMITTER_ENTITY_ID)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Novy Cooker Hood"
    assert result["data"] == {
        CONF_TRANSMITTER: entity_entry.id,
        CONF_CODE: 3,
    }
    assert result["result"].unique_id == f"{entity_entry.id}_3"


async def test_user_flow_retry_picks_different_code(
    hass: HomeAssistant,
    mock_get_codes: MagicMock,
    mock_rf_entity: MockRadioFrequencyEntity,
    entity_registry: er.EntityRegistry,
) -> None:
    """Retry returns to the user step; a new code re-fires the test and saves."""
    result = await _start_user_flow(hass, code="1")
    assert result["type"] is FlowResultType.MENU

    # Pick Retry → back to user step.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "retry"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Submit a different code → test fires again, menu shown.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_TRANSMITTER: TRANSMITTER_ENTITY_ID,
            CONF_CODE: "7",
        },
    )
    assert result["type"] is FlowResultType.MENU
    # One load per test x two tests; two sends per test x two tests.
    assert mock_get_codes.async_load_command.await_count == 2
    assert len(mock_rf_entity.send_command_calls) == 4

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "finish"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CODE] == 7


async def test_user_flow_test_transmit_failure(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
) -> None:
    """A transmit failure surfaces as a `test_failed` menu with a Retry option."""
    with patch(
        "homeassistant.components.novy_cooker_hood.config_flow.async_send_command",
        side_effect=HomeAssistantError("nope"),
    ):
        result = await _start_user_flow(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "test_failed"


async def test_unique_id_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test aborting when the same transmitter+code is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_TRANSMITTER: TRANSMITTER_ENTITY_ID,
            CONF_CODE: "1",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_same_transmitter_different_code_is_allowed(
    hass: HomeAssistant,
    mock_get_codes: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_rf_entity: MockRadioFrequencyEntity,
    entity_registry: er.EntityRegistry,
) -> None:
    """A second hood on the same transmitter but a different code is allowed."""
    mock_config_entry.add_to_hass(hass)

    result = await _start_user_flow(hass, code="5")
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "finish"}
    )
    entity_entry = entity_registry.async_get(TRANSMITTER_ENTITY_ID)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CODE] == 5
    assert result["result"].unique_id == f"{entity_entry.id}_5"


async def test_no_transmitters(hass: HomeAssistant) -> None:
    """Test the flow aborts when no RF transmitters are registered at all."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_transmitters"


async def test_no_compatible_transmitters(hass: HomeAssistant) -> None:
    """Test aborting when transmitters exist but none support 433.92 MHz OOK."""
    assert await async_setup_component(hass, RF_DOMAIN, {})
    await hass.async_block_till_done()
    incompatible = MockRadioFrequencyEntity(
        "incompatible", frequency_ranges=[(868_000_000, 869_000_000)]
    )
    await hass.data[DATA_COMPONENT].async_add_entities([incompatible])

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_compatible_transmitters"
