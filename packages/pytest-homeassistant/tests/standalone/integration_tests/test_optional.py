"""Test fixtures with optional dependencies."""

from infrared_protocols.commands.nec import NECCommand
import pytest

from homeassistant.components import bluetooth, infrared, radio_frequency
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant.components.bluetooth import (
    HCI0_SOURCE_ADDRESS,
    HCI1_SOURCE_ADDRESS,
    NON_CONNECTABLE_REMOTE_SOURCE_ADDRESS,
)
from pytest_homeassistant.components.infrared.common import (
    MockInfraredEmitterEntity,
    MockInfraredReceiverEntity,
)
from pytest_homeassistant.components.radio_frequency.common import (
    MockRadioFrequencyCommand,
    MockRadioFrequencyEntity,
)


@pytest.fixture
async def bluetooth_manager(hass: HomeAssistant) -> None:
    """Set up the Bluetooth manager."""
    assert await async_setup_component(hass, bluetooth.DOMAIN, {})
    await hass.async_block_till_done()


@pytest.mark.usefixtures(
    "bluetooth_manager",
    "register_hci0_scanner",
    "register_hci1_scanner",
    "register_non_connectable_scanner",
)
async def test_bluetooth_scanners(hass: HomeAssistant) -> None:
    """Test registration of connectable and non-connectable scanners."""
    scanners = {
        scanner.source: scanner for scanner in bluetooth.async_current_scanners(hass)
    }
    assert scanners[HCI0_SOURCE_ADDRESS].connectable
    assert scanners[HCI1_SOURCE_ADDRESS].connectable
    assert not scanners[NON_CONNECTABLE_REMOTE_SOURCE_ADDRESS].connectable


@pytest.mark.usefixtures("enable_bluetooth", "macos_adapter")
async def test_bluetooth_macos_adapter(hass: HomeAssistant) -> None:
    """Test reloading Bluetooth with a mocked macOS adapter."""
    entry = hass.config_entries.async_entries(bluetooth.DOMAIN)[0]
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED


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
