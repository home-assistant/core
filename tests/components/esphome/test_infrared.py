"""Test ESPHome infrared platform."""

from aioesphomeapi import (
    APIClient,
    APIConnectionError,
    InfraredCapability,
    InfraredInfo,
)
from infrared_protocols import NECCommand
import pytest

from homeassistant.components import infrared
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
    ("capabilities", "entity_created"),
    [
        (InfraredCapability.TRANSMITTER, True),
        (InfraredCapability.RECEIVER, False),
        (InfraredCapability.TRANSMITTER | InfraredCapability.RECEIVER, True),
        (InfraredCapability(0), False),
    ],
)
async def test_infrared_entity_transmitter(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    capabilities: InfraredCapability,
    entity_created: bool,
) -> None:
    """Test infrared entity with transmitter capability is created."""
    await _mock_ir_device(mock_esphome_device, mock_client, capabilities)

    state = hass.states.get(ENTITY_ID)
    assert (state is not None) == entity_created

    emitters = infrared.async_get_emitters(hass)
    assert (len(emitters) == 1) == entity_created


async def test_infrared_multiple_entities_mixed_capabilities(
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
        InfraredInfo(
            object_id="ir_transceiver",
            key=3,
            name="IR Transceiver",
            capabilities=InfraredCapability.TRANSMITTER | InfraredCapability.RECEIVER,
        ),
    ]
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=[],
    )

    # Only transmitter and transceiver should be created
    assert hass.states.get("infrared.test_ir_transmitter") is not None
    assert hass.states.get("infrared.test_ir_receiver") is None
    assert hass.states.get("infrared.test_ir_transceiver") is not None

    emitters = infrared.async_get_emitters(hass)
    assert len(emitters) == 2


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
