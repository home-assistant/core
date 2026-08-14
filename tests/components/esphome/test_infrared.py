"""Test ESPHome infrared platform."""

from aioesphomeapi import (
    APIClient,
    APIConnectionError,
    InfraredCapability,
    InfraredInfo,
)
from aioesphomeapi.client import InfraredRFReceiveEventModel
from infrared_protocols.commands.nec import NECCommand
import pytest

from homeassistant.components import infrared
from homeassistant.components.infrared import (
    DATA_COMPONENT,
    InfraredDeviceClass,
    InfraredReceivedSignal,
    InfraredReceiverEntity,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import MockESPHomeDevice, MockESPHomeDeviceType

ENTITY_ID = "infrared.test_ir"


async def _mock_ir_device(
    mock_esphome_device: MockESPHomeDeviceType,
    mock_client: APIClient,
    capabilities: InfraredCapability = InfraredCapability.TRANSMITTER,
) -> MockESPHomeDevice:
    entity_info = [
        InfraredInfo(object_id="ir", key=1, name="IR", capabilities=capabilities)
    ]
    return await mock_esphome_device(
        mock_client=mock_client, entity_info=entity_info, states=[]
    )


@pytest.mark.parametrize(
    ("capabilities", "expected_device_class", "emitter_count", "receiver_count"),
    [
        pytest.param(
            InfraredCapability.TRANSMITTER,
            InfraredDeviceClass.EMITTER,
            1,
            0,
            id="transmitter",
        ),
        pytest.param(
            InfraredCapability.RECEIVER,
            InfraredDeviceClass.RECEIVER,
            0,
            1,
            id="receiver",
        ),
    ],
)
async def test_infrared_entity_single_capability(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    capabilities: InfraredCapability,
    expected_device_class: InfraredDeviceClass,
    emitter_count: int,
    receiver_count: int,
) -> None:
    """Test infrared entity is created with the right device class per capability."""
    await _mock_ir_device(mock_esphome_device, mock_client, capabilities)

    state = hass.states.get(ENTITY_ID)
    assert (state is not None) == (expected_device_class is not None)
    assert state.attributes["device_class"] == expected_device_class

    emitters = infrared.async_get_emitters(hass)
    assert len(emitters) == emitter_count
    receivers = infrared.async_get_receivers(hass)
    assert len(receivers) == receiver_count


async def test_infrared_entity_dual_capability(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test multiple infrared entities with mixed capabilities."""
    entity_info = [
        InfraredInfo(
            object_id="ir_transmitter",
            key=1,
            name="IR Transmitter",
            capabilities=InfraredCapability.TRANSMITTER,
        ),
        InfraredInfo(
            object_id="ir_receiver",
            key=2,
            name="IR Receiver",
            capabilities=InfraredCapability.RECEIVER,
        ),
    ]
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=[],
    )

    transmitter_state = hass.states.get("infrared.test_ir_transmitter")
    assert transmitter_state is not None
    assert transmitter_state.attributes["device_class"] == InfraredDeviceClass.EMITTER

    receiver_state = hass.states.get("infrared.test_ir_receiver")
    assert receiver_state is not None
    assert receiver_state.attributes["device_class"] == InfraredDeviceClass.RECEIVER

    emitters = infrared.async_get_emitters(hass)
    assert len(emitters) == 1
    receivers = infrared.async_get_receivers(hass)
    assert len(receivers) == 1


async def test_infrared_send_command_success(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test sending IR command successfully."""
    await _mock_ir_device(mock_esphome_device, mock_client)

    command = NECCommand(address=0x04, command=0x08, modulation=38000)
    await infrared.async_send_command(hass, ENTITY_ID, command)

    # Verify the command was sent to the ESPHome client
    mock_client.infrared_rf_transmit_raw_timings.assert_called_once()
    call_args = mock_client.infrared_rf_transmit_raw_timings.call_args
    assert call_args[0][0] == 1  # key
    assert call_args[1]["carrier_frequency"] == 38000
    assert call_args[1]["device_id"] == 0

    # Verify timings (alternating positive/negative values)
    timings = call_args[1]["timings"]
    assert len(timings) > 0
    for i in range(0, len(timings), 2):
        assert timings[i] >= 0
    for i in range(1, len(timings), 2):
        assert timings[i] <= 0


async def test_infrared_send_command_failure(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test sending IR command with APIConnectionError raises HomeAssistantError."""
    await _mock_ir_device(mock_esphome_device, mock_client)

    mock_client.infrared_rf_transmit_raw_timings.side_effect = APIConnectionError(
        "Connection lost"
    )

    command = NECCommand(address=0x04, command=0x08, modulation=38000)

    with pytest.raises(HomeAssistantError) as exc_info:
        await infrared.async_send_command(hass, ENTITY_ID, command)
    assert exc_info.value.translation_domain == "esphome"
    assert exc_info.value.translation_key == "error_communicating_with_device"


async def test_infrared_receiver_signal_dispatched(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test receiver subscribes to events and dispatches received signals."""
    await _mock_ir_device(
        mock_esphome_device, mock_client, capabilities=InfraredCapability.RECEIVER
    )

    mock_client.subscribe_infrared_rf_receive.assert_called_once()
    on_event = mock_client.subscribe_infrared_rf_receive.call_args[0][0]

    receiver = hass.data[DATA_COMPONENT].get_entity(ENTITY_ID)
    assert isinstance(receiver, InfraredReceiverEntity)
    received_signals: list[InfraredReceivedSignal] = []
    receiver.async_subscribe_received_signal(received_signals.append)

    timings = [100, -200, 300]
    on_event(InfraredRFReceiveEventModel(key=1, device_id=0, timings=timings))
    await hass.async_block_till_done()

    assert received_signals == [InfraredReceivedSignal(timings=timings)]
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE

    # Test events with wrong key/device_id are ignored
    on_event(InfraredRFReceiveEventModel(key=99, device_id=0, timings=timings))
    on_event(InfraredRFReceiveEventModel(key=1, device_id=42, timings=timings))
    await hass.async_block_till_done()
    assert len(received_signals) == 1


async def test_infrared_receiver_unsubscribes_on_unload(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test receiver unsubscribes from device events when its entry is unloaded."""
    mock_device = await _mock_ir_device(
        mock_esphome_device, mock_client, capabilities=InfraredCapability.RECEIVER
    )

    unsub = mock_client.subscribe_infrared_rf_receive.return_value
    unsub.assert_not_called()

    await hass.config_entries.async_unload(mock_device.entry.entry_id)
    await hass.async_block_till_done()

    unsub.assert_called_once()


async def test_infrared_receiver_resubscribes_on_reconnect(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test receiver re-subscribes to events after a reconnect."""
    mock_device = await _mock_ir_device(
        mock_esphome_device, mock_client, capabilities=InfraredCapability.RECEIVER
    )

    assert mock_client.subscribe_infrared_rf_receive.call_count == 1

    await mock_device.mock_disconnect(False)
    await hass.async_block_till_done()
    await mock_device.mock_connect()
    await hass.async_block_till_done()

    assert mock_client.subscribe_infrared_rf_receive.call_count == 2


async def test_infrared_entity_availability(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test infrared entity becomes available after device reconnects."""
    mock_device = await _mock_ir_device(mock_esphome_device, mock_client)

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
