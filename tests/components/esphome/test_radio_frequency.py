"""Test ESPHome radio frequency platform."""

from aioesphomeapi import (
    APIClient,
    APIConnectionError,
    RadioFrequencyCapability,
    RadioFrequencyInfo,
    RadioFrequencyModulation,
)
import pytest
from rf_protocols import ModulationType, OOKCommand

from homeassistant.components import radio_frequency
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import MockESPHomeDevice, MockESPHomeDeviceType

ENTITY_ID = "radio_frequency.test_rf"


async def _mock_rf_device(
    mock_esphome_device: MockESPHomeDeviceType,
    mock_client: APIClient,
    capabilities: RadioFrequencyCapability = RadioFrequencyCapability.TRANSMITTER,
    frequency_min: int = 433_000_000,
    frequency_max: int = 434_000_000,
    supported_modulations: int = 1,
) -> MockESPHomeDevice:
    entity_info = [
        RadioFrequencyInfo(
            object_id="rf",
            key=1,
            name="RF",
            capabilities=capabilities,
            frequency_min=frequency_min,
            frequency_max=frequency_max,
            supported_modulations=supported_modulations,
        )
    ]
    return await mock_esphome_device(
        mock_client=mock_client, entity_info=entity_info, states=[]
    )


@pytest.mark.parametrize(
    ("capabilities", "entity_created"),
    [
        (RadioFrequencyCapability.TRANSMITTER, True),
        (RadioFrequencyCapability.RECEIVER, False),
        (
            RadioFrequencyCapability.TRANSMITTER | RadioFrequencyCapability.RECEIVER,
            True,
        ),
        (RadioFrequencyCapability(0), False),
    ],
)
async def test_radio_frequency_entity_transmitter(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    capabilities: RadioFrequencyCapability,
    entity_created: bool,
) -> None:
    """Test radio frequency entity with transmitter capability is created."""
    await _mock_rf_device(mock_esphome_device, mock_client, capabilities)

    state = hass.states.get(ENTITY_ID)
    assert (state is not None) == entity_created


async def test_radio_frequency_multiple_entities_mixed_capabilities(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test multiple radio frequency entities with mixed capabilities."""
    entity_info = [
        RadioFrequencyInfo(
            object_id="rf_transmitter",
            key=1,
            name="RF Transmitter",
            capabilities=RadioFrequencyCapability.TRANSMITTER,
        ),
        RadioFrequencyInfo(
            object_id="rf_receiver",
            key=2,
            name="RF Receiver",
            capabilities=RadioFrequencyCapability.RECEIVER,
        ),
        RadioFrequencyInfo(
            object_id="rf_transceiver",
            key=3,
            name="RF Transceiver",
            capabilities=(
                RadioFrequencyCapability.TRANSMITTER | RadioFrequencyCapability.RECEIVER
            ),
        ),
    ]
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=[],
    )

    # Only transmitter and transceiver should be created
    assert hass.states.get("radio_frequency.test_rf_transmitter") is not None
    assert hass.states.get("radio_frequency.test_rf_receiver") is None
    assert hass.states.get("radio_frequency.test_rf_transceiver") is not None


async def test_radio_frequency_send_command_success(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test sending RF command successfully."""
    await _mock_rf_device(mock_esphome_device, mock_client)

    command = OOKCommand(
        frequency=433_920_000,
        timings=[350, -1050, 350, -350],
    )
    await radio_frequency.async_send_command(hass, ENTITY_ID, command)

    mock_client.radio_frequency_transmit_raw_timings.assert_called_once()
    call_args = mock_client.radio_frequency_transmit_raw_timings.call_args
    assert call_args[0][0] == 1  # key
    assert call_args[1]["frequency"] == 433_920_000
    assert call_args[1]["modulation"] == RadioFrequencyModulation.OOK
    assert call_args[1]["repeat_count"] == 1
    assert call_args[1]["device_id"] == 0
    assert call_args[1]["timings"] == [350, -1050, 350, -350]


async def test_radio_frequency_send_command_failure(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test sending RF command with APIConnectionError raises HomeAssistantError."""
    await _mock_rf_device(mock_esphome_device, mock_client)

    mock_client.radio_frequency_transmit_raw_timings.side_effect = APIConnectionError(
        "Connection lost"
    )

    command = OOKCommand(
        frequency=433_920_000,
        timings=[350, -1050],
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await radio_frequency.async_send_command(hass, ENTITY_ID, command)
    assert exc_info.value.translation_domain == "esphome"
    assert exc_info.value.translation_key == "error_communicating_with_device"


async def test_radio_frequency_entity_availability(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test radio frequency entity becomes available after device reconnects."""
    mock_device = await _mock_rf_device(mock_esphome_device, mock_client)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    await mock_device.mock_disconnect(False)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    await mock_device.mock_connect()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_radio_frequency_supported_frequency_ranges(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test supported frequency ranges are exposed from device info."""
    await _mock_rf_device(
        mock_esphome_device,
        mock_client,
        frequency_min=433_000_000,
        frequency_max=434_000_000,
    )

    transmitters = radio_frequency.async_get_transmitters(
        hass, 433_920_000, ModulationType.OOK
    )
    assert len(transmitters) == 1

    transmitters = radio_frequency.async_get_transmitters(
        hass, 868_000_000, ModulationType.OOK
    )
    assert len(transmitters) == 0
