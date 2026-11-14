"""Tests for the Somfy RTS config flow."""

import pytest
from rf_protocols import SomfyRTSButton
from unittest.mock import patch

from homeassistant.components.radio_frequency import DATA_COMPONENT, DOMAIN as RF_DOMAIN
from homeassistant.components.somfy_rts.const import CONF_ADDRESS, CONF_ROLLING_CODE, CONF_TRANSMITTER, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.radio_frequency.common import MockRadioFrequencyEntity

from .conftest import ADDRESS, ADDRESS_HEX, TRANSMITTER_ENTITY_ID


async def test_user_flow_without_prog(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test completing the flow without sending PROG creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ADDRESS: ADDRESS_HEX, CONF_TRANSMITTER: TRANSMITTER_ENTITY_ID},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "prog"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"send_prog": False},
    )

    entity_entry = entity_registry.async_get(TRANSMITTER_ENTITY_ID)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Somfy RTS {ADDRESS_HEX}"
    assert result["data"] == {
        CONF_ADDRESS: ADDRESS,
        CONF_TRANSMITTER: entity_entry.id,
        CONF_ROLLING_CODE: 0,
    }
    assert result["result"].unique_id == ADDRESS_HEX


@pytest.mark.parametrize(
    "address_input",
    ["not-hex", "000000", "1000000", ""],
)
async def test_invalid_address(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    address_input: str,
) -> None:
    """Test that an out-of-range or non-hex address shows a validation error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ADDRESS: address_input, CONF_TRANSMITTER: TRANSMITTER_ENTITY_ID},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_ADDRESS: "invalid_address"}


async def test_unique_id_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test aborting when the same remote address is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ADDRESS: ADDRESS_HEX, CONF_TRANSMITTER: TRANSMITTER_ENTITY_ID},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_no_transmitters(hass: HomeAssistant) -> None:
    """Test aborting when no RF transmitters are registered at all."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_transmitters"


async def test_no_compatible_transmitters(hass: HomeAssistant) -> None:
    """Test aborting when transmitters exist but none support 433.42 MHz OOK."""
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


async def test_send_prog_during_flow(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
) -> None:
    """Test checking Send PROG transmits a PROG command and re-shows the prog step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ADDRESS: ADDRESS_HEX, CONF_TRANSMITTER: TRANSMITTER_ENTITY_ID},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "prog"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"send_prog": True},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "prog"
    assert not result["errors"]

    assert len(mock_rf_entity.send_command_calls) == 1
    sent = mock_rf_entity.send_command_calls[0]
    assert sent.command.button == SomfyRTSButton.PROG
    assert sent.command.address == ADDRESS
    assert sent.command.frame_repeats == 4


async def test_send_prog_increments_rolling_code_in_entry_data(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that PROG commands during the flow are counted in entry data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ADDRESS: ADDRESS_HEX, CONF_TRANSMITTER: TRANSMITTER_ENTITY_ID},
    )
    for _ in range(2):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"send_prog": True},
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"send_prog": False},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ROLLING_CODE] == 2


async def test_send_prog_shows_error_when_command_fails(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a failed PROG command shows prog_failed and does not increment the rolling code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ADDRESS: ADDRESS_HEX, CONF_TRANSMITTER: TRANSMITTER_ENTITY_ID},
    )

    with patch(
        "homeassistant.components.somfy_rts.config_flow.async_send_command",
        side_effect=HomeAssistantError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"send_prog": True},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "prog"
    assert result["errors"] == {"base": "prog_failed"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"send_prog": False},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ROLLING_CODE] == 0
