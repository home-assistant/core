"""Test the Intertechno TriState config flow."""

from typing import Any

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.radio_frequency.common import (
    MockRadioFrequencyEntity,
)

from homeassistant.components.intertechno_tristate.const import (
    CONF_CHANNEL,
    CONF_GROUP,
    CONF_HOUSECODE,
    CONF_TRANSMITTER,
    DOMAIN,
)
from rf_protocols.commands.pt2262 import ITTristateCommand
from homeassistant.components.radio_frequency import DATA_COMPONENT, DOMAIN as RF_DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

TRANSMITTER_ENTITY_ID = "radio_frequency.test_rf_transmitter"
MAX_CHANNEL = ITTristateCommand.MAX_CHANNEL
MAX_GROUP = ITTristateCommand.MAX_GROUP


async def _start_user_flow(hass: HomeAssistant) -> dict:
    """Start user flow and assert first form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result


async def test_user_flow(
    hass: HomeAssistant, mock_rf_entity: MockRadioFrequencyEntity
) -> None:
    """Test successful user flow creates an entry."""
    result = await _start_user_flow(hass)

    user_input = {
        CONF_TRANSMITTER: TRANSMITTER_ENTITY_ID,
        CONF_HOUSECODE: "A",
        CONF_GROUP: 1,
        CONF_CHANNEL: 1,
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing_mode"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert len(mock_rf_entity.send_command_calls) == 1
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing_result"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"device_responded": True}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Intertechno TriState HC A G 1 CH 1"
    assert result["data"] == user_input


async def test_user_flow_retry_learn(
    hass: HomeAssistant, mock_rf_entity: MockRadioFrequencyEntity
) -> None:
    """Test the user can retry pairing when the device does not respond."""
    result = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_TRANSMITTER: TRANSMITTER_ENTITY_ID,
            CONF_HOUSECODE: "A",
            CONF_GROUP: 1,
            CONF_CHANNEL: 1,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing_mode"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert len(mock_rf_entity.send_command_calls) == 1
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing_result"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"device_responded": False}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing_mode"
    assert result["errors"] == {"base": "no_response"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert len(mock_rf_entity.send_command_calls) == 2
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing_result"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"device_responded": True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("invalid_field", "invalid_value", "expected_error"),
    [
        pytest.param(CONF_HOUSECODE, "Q", "invalid_housecode", id="invalid_housecode"),
        pytest.param(CONF_GROUP, MAX_GROUP + 1, "invalid_group", id="invalid_group"),
        pytest.param(
            CONF_CHANNEL, MAX_CHANNEL + 1, "invalid_channel", id="invalid_channel"
        ),
    ],
)
async def test_invalid_user_input(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    invalid_field: str,
    invalid_value: str | int,
    expected_error: str,
) -> None:
    """Test validation errors on user input and recovery to completion."""
    result = await _start_user_flow(hass)

    valid_input: dict[str, Any] = {
        CONF_TRANSMITTER: TRANSMITTER_ENTITY_ID,
        CONF_HOUSECODE: "A",
        CONF_GROUP: 1,
        CONF_CHANNEL: 1,
    }
    invalid_input = {**valid_input, invalid_field: invalid_value}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=invalid_input,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {invalid_field: expected_error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=valid_input,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing_mode"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert len(mock_rf_entity.send_command_calls) == 1
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing_result"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"device_responded": True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Intertechno TriState HC A G 1 CH 1"
    assert result["data"] == valid_input


async def test_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test aborting when same transmitter/housecode/channel/group is configured."""
    mock_config_entry.add_to_hass(hass)

    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_TRANSMITTER: TRANSMITTER_ENTITY_ID,
            CONF_HOUSECODE: "A",
            CONF_GROUP: 1,
            CONF_CHANNEL: 1,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_no_transmitters(hass: HomeAssistant) -> None:
    """Test flow aborts when no RF transmitters are set up."""
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
