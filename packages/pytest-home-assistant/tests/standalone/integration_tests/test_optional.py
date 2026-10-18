"""Test fixtures with optional dependencies."""

from infrared_protocols.commands.nec import NECCommand
import pytest

from homeassistant.components import infrared, radio_frequency
from homeassistant.core import HomeAssistant
from pytest_homeassistant.components.infrared.common import (
    MockInfraredEmitterEntity,
    MockInfraredReceiverEntity,
)
from pytest_homeassistant.components.radio_frequency.common import (
    MockRadioFrequencyCommand,
    MockRadioFrequencyEntity,
)


@pytest.mark.usefixtures("init_infrared")
async def test_infrared_setup(hass: HomeAssistant) -> None:
    """Test infrared setup without entities."""
    assert infrared.DOMAIN in hass.config.components
    assert infrared.async_get_emitters(hass) == []
    assert infrared.async_get_receivers(hass) == []


async def test_infrared_entities(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test infrared entity discovery and command delivery."""
    assert infrared.async_get_emitters(hass) == [mock_infrared_emitter_entity.entity_id]
    assert infrared.async_get_receivers(hass) == [
        mock_infrared_receiver_entity.entity_id
    ]
    command = NECCommand(address=0x04FB, command=0xF7, modulation=38000)
    await infrared.async_send_command(
        hass, mock_infrared_emitter_entity.entity_id, command
    )
    assert mock_infrared_emitter_entity.send_command_calls == [command]


@pytest.mark.usefixtures("init_radio_frequency")
async def test_radio_frequency_setup(hass: HomeAssistant) -> None:
    """Test radio frequency setup without entities."""
    assert radio_frequency.DOMAIN in hass.config.components
    assert not hass.data[radio_frequency.DATA_COMPONENT].entities


async def test_radio_frequency_entity(
    hass: HomeAssistant, mock_rf_entity: MockRadioFrequencyEntity
) -> None:
    """Test radio frequency entity discovery and command delivery."""
    command = MockRadioFrequencyCommand()
    assert radio_frequency.async_get_transmitters(
        hass, command.frequency, command.modulation
    ) == [mock_rf_entity.entity_id]
    await radio_frequency.async_send_command(hass, mock_rf_entity.entity_id, command)
    assert len(mock_rf_entity.send_command_calls) == 1
    assert mock_rf_entity.send_command_calls[0].command is command
