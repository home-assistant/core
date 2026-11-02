"""Test ESPHome radio frequency platform."""

from aioesphomeapi import (
    APIClient,
    APIConnectionError,
    RadioFrequencyCapability,
    RadioFrequencyInfo,
    RadioFrequencyModulation,
)
from aioesphomeapi.client import InfraredRFReceiveEventModel
from freezegun.api import FrozenDateTimeFactory
import pytest
from rf_protocols import ModulationType
from rf_protocols.commands.ook import OOKCommand

from homeassistant.components import radio_frequency
from homeassistant.components.radio_frequency import (
    DATA_COMPONENT,
    RadioFrequencyDeviceClass,
    RadioFrequencyReceivedSignal,
    RadioFrequencyReceiverEntity,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

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
    ("capabilities", "expected_device_class", "subscribe_count"),
    [
        pytest.param(
            RadioFrequencyCapability.TRANSMITTER,
            RadioFrequencyDeviceClass.TRANSMITTER,
            0,
            id="transmitter",
        ),
        pytest.param(
            RadioFrequencyCapability.RECEIVER,
            RadioFrequencyDeviceClass.RECEIVER,
            1,
            id="receiver",
        ),
        pytest.param(
            RadioFrequencyCapability.TRANSMITTER | RadioFrequencyCapability.RECEIVER,
            RadioFrequencyDeviceClass.RECEIVER,
            1,
            id="transceiver",
        ),
    ],
)
async def test_radio_frequency_entity_capabilities(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    capabilities: RadioFrequencyCapability,
    expected_device_class: RadioFrequencyDeviceClass,
    subscribe_count: int,
) -> None:
    """Test radio frequency entity is created with the right device class."""
    await _mock_rf_device(mock_esphome_device, mock_client, capabilities)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["device_class"] == expected_device_class
    assert mock_client.subscribe_infrared_rf_receive.call_count == subscribe_count


async def test_radio_frequency_entity_no_capabilities(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test radio frequency entity without capabilities is not created."""
    await _mock_rf_device(mock_esphome_device, mock_client, RadioFrequencyCapability(0))

    assert hass.states.get(ENTITY_ID) is None


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

    for entity_id, expected_device_class in (
        ("radio_frequency.test_rf_transmitter", RadioFrequencyDeviceClass.TRANSMITTER),
        ("radio_frequency.test_rf_receiver", RadioFrequencyDeviceClass.RECEIVER),
        ("radio_frequency.test_rf_transceiver", RadioFrequencyDeviceClass.RECEIVER),
    ):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.attributes["device_class"] == expected_device_class


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


async def test_radio_frequency_receiver_signal_dispatched(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test receiver subscribes to events and dispatches received signals."""
    now = dt_util.utcnow()
    freezer.move_to(now)
    await _mock_rf_device(
        mock_esphome_device,
        mock_client,
        capabilities=RadioFrequencyCapability.RECEIVER,
    )

    mock_client.subscribe_infrared_rf_receive.assert_called_once()
    on_event = mock_client.subscribe_infrared_rf_receive.call_args[0][0]

    receiver = hass.data[DATA_COMPONENT].get_entity(ENTITY_ID)
    assert isinstance(receiver, RadioFrequencyReceiverEntity)
    received_signals: list[RadioFrequencyReceivedSignal] = []
    receiver.async_subscribe_received_signal(received_signals.append)

    timings = [350, -1050, 350, -350]
    on_event(InfraredRFReceiveEventModel(key=1, device_id=0, timings=timings))
    await hass.async_block_till_done()

    assert received_signals == [RadioFrequencyReceivedSignal(timings=timings)]
    assert hass.states.get(ENTITY_ID).state == now.isoformat(timespec="milliseconds")

    # Test events with wrong key/device_id are ignored
    on_event(InfraredRFReceiveEventModel(key=99, device_id=0, timings=timings))
    on_event(InfraredRFReceiveEventModel(key=1, device_id=42, timings=timings))
    await hass.async_block_till_done()
    assert len(received_signals) == 1


async def test_radio_frequency_receiver_unsubscribes_on_unload(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test receiver unsubscribes from device events when its entry is unloaded."""
    mock_device = await _mock_rf_device(
        mock_esphome_device,
        mock_client,
        capabilities=RadioFrequencyCapability.RECEIVER,
    )

    unsub = mock_client.subscribe_infrared_rf_receive.return_value
    unsub.assert_not_called()

    await hass.config_entries.async_unload(mock_device.entry.entry_id)
    await hass.async_block_till_done()

    unsub.assert_called_once()


async def test_radio_frequency_receiver_resubscribes_on_reconnect(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test receiver re-subscribes to events after a reconnect."""
    mock_device = await _mock_rf_device(
        mock_esphome_device,
        mock_client,
        capabilities=RadioFrequencyCapability.RECEIVER,
    )

    assert mock_client.subscribe_infrared_rf_receive.call_count == 1

    await mock_device.mock_disconnect(False)
    await hass.async_block_till_done()
    await mock_device.mock_connect()
    await hass.async_block_till_done()

    assert mock_client.subscribe_infrared_rf_receive.call_count == 2


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
