"""Tests for the Radio Frequency consumer entity helpers."""

from typing import override

import pytest
from pytest_homeassistant.common import MockEntityPlatform
from pytest_homeassistant.components.common import (
    assert_availability_follows_source_entity,
)
from pytest_homeassistant.components.radio_frequency import (
    ENTITY_ID,
    RECEIVER_ENTITY_ID,
)
from pytest_homeassistant.components.radio_frequency.common import (
    MockRadioFrequencyCommand,
    MockRadioFrequencyEntity,
    MockRadioFrequencyReceiverEntity,
)

from homeassistant.components.radio_frequency import (
    RadioFrequencyReceivedSignal,
    RadioFrequencyReceiverConsumerEntity,
    RadioFrequencyTransmitterConsumerEntity,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback

CONSUMER_ENTITY_ID = "test_domain.consumer"

TEST_SIGNAL = RadioFrequencyReceivedSignal(
    timings=[350, -1050, 350, -350], frequency=433_920_000
)


class MockConsumerEntity(
    RadioFrequencyTransmitterConsumerEntity, RadioFrequencyReceiverConsumerEntity
):
    """Mock entity consuming an RF transmitter and an RF receiver."""

    _attr_name = "Consumer"

    def __init__(self, transmitter: str, receiver: str) -> None:
        """Initialize the mock consumer entity."""
        self._rf_transmitter_entity_id = transmitter
        self._rf_receiver_entity_id = receiver
        self.received_signals: list[RadioFrequencyReceivedSignal] = []

    @callback
    @override
    def _handle_signal(self, signal: RadioFrequencyReceivedSignal) -> None:
        """Store the received signal."""
        self.received_signals.append(signal)


@pytest.fixture
async def mock_consumer_entity(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    mock_rf_receiver_entity: MockRadioFrequencyReceiverEntity,
) -> MockConsumerEntity:
    """Add a consumer entity referencing the RF entities."""
    entity = MockConsumerEntity(ENTITY_ID, RECEIVER_ENTITY_ID)
    await MockEntityPlatform(hass).async_add_entities([entity])
    await hass.async_block_till_done()
    return entity


@pytest.mark.usefixtures("mock_consumer_entity")
async def test_availability_follows_rf_entities(hass: HomeAssistant) -> None:
    """Test the consumer is available only while all RF entities are available."""
    await assert_availability_follows_source_entity(
        hass, CONSUMER_ENTITY_ID, [ENTITY_ID, RECEIVER_ENTITY_ID]
    )


async def test_send_command(
    mock_rf_entity: MockRadioFrequencyEntity,
    mock_consumer_entity: MockConsumerEntity,
) -> None:
    """Test the consumer sends commands through the transmitter."""
    command = MockRadioFrequencyCommand()
    await mock_consumer_entity._send_command(command)

    assert len(mock_rf_entity.send_command_calls) == 1
    assert mock_rf_entity.send_command_calls[0].command is command


async def test_receiver_resubscribes_after_receiver_unavailable(
    hass: HomeAssistant,
    mock_rf_receiver_entity: MockRadioFrequencyReceiverEntity,
    mock_consumer_entity: MockConsumerEntity,
) -> None:
    """Test the consumer resubscribes when the receiver becomes available again."""
    hass.states.async_set(RECEIVER_ENTITY_ID, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert (state := hass.states.get(CONSUMER_ENTITY_ID)) is not None
    assert state.state == STATE_UNAVAILABLE

    hass.states.async_set(RECEIVER_ENTITY_ID, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert (state := hass.states.get(CONSUMER_ENTITY_ID)) is not None
    assert state.state != STATE_UNAVAILABLE

    mock_rf_receiver_entity._handle_received_signal(TEST_SIGNAL)
    assert mock_consumer_entity.received_signals == [TEST_SIGNAL]


async def test_receiver_unsubscribed_on_remove(
    mock_rf_receiver_entity: MockRadioFrequencyReceiverEntity,
    mock_consumer_entity: MockConsumerEntity,
) -> None:
    """Test the consumer unsubscribes from the receiver when removed."""
    await mock_consumer_entity.async_remove()

    mock_rf_receiver_entity._handle_received_signal(TEST_SIGNAL)
    assert mock_consumer_entity.received_signals == []
