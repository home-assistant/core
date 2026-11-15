"""Tests for the Radio Frequency integration setup."""

import re
from unittest.mock import AsyncMock, Mock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
    mock_restore_cache,
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
from rf_protocols import ModulationType

from homeassistant.components.radio_frequency import (
    DATA_COMPONENT,
    DOMAIN,
    RadioFrequencyReceivedSignal,
    async_get_receivers,
    async_get_transmitters,
    async_send_command,
    async_subscribe_receiver,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

TEST_DOMAIN = "test"


async def test_get_transmitters_component_not_loaded(hass: HomeAssistant) -> None:
    """Test getting transmitters raises when the component is not loaded."""
    with pytest.raises(HomeAssistantError, match="component_not_loaded"):
        async_get_transmitters(hass, 433_920_000, ModulationType.OOK)


@pytest.mark.usefixtures("init_radio_frequency")
async def test_get_transmitters_no_entities(hass: HomeAssistant) -> None:
    """Test getting transmitters raises when none are registered."""
    with pytest.raises(
        HomeAssistantError,
        match="No Radio Frequency transmitters available",
    ):
        async_get_transmitters(hass, 433_920_000, ModulationType.OOK)


@pytest.mark.usefixtures("mock_rf_entity")
async def test_get_transmitters_with_frequency_ranges(hass: HomeAssistant) -> None:
    """Test transmitter with frequency ranges filters correctly."""
    # 433.92 MHz is within 433-434 MHz range
    result = async_get_transmitters(hass, 433_920_000, ModulationType.OOK)
    assert result == [ENTITY_ID]

    # 868 MHz is outside the range
    result = async_get_transmitters(hass, 868_000_000, ModulationType.OOK)
    assert result == []


@pytest.mark.usefixtures("mock_rf_entity")
async def test_get_transmitters_filters_by_modulation(hass: HomeAssistant) -> None:
    """Test transmitters are filtered by supported modulation."""
    result = async_get_transmitters(hass, 433_920_000, "no_matching_modulation")  # type: ignore[arg-type]
    assert result == []


@pytest.mark.usefixtures("mock_rf_receiver_entity")
async def test_get_transmitters_ignores_receivers(hass: HomeAssistant) -> None:
    """Test receivers are not returned as transmitters."""
    with pytest.raises(
        HomeAssistantError,
        match="No Radio Frequency transmitters available",
    ):
        async_get_transmitters(hass, 433_920_000, ModulationType.OOK)


async def test_get_receivers_component_not_loaded(hass: HomeAssistant) -> None:
    """Test getting receivers raises when the component is not loaded."""
    with pytest.raises(HomeAssistantError, match="component_not_loaded"):
        async_get_receivers(hass, 433_920_000, ModulationType.OOK)


@pytest.mark.usefixtures("mock_rf_entity")
async def test_get_receivers_no_receivers(hass: HomeAssistant) -> None:
    """Test getting receivers raises when none are registered."""
    with pytest.raises(
        HomeAssistantError,
        match="No Radio Frequency receivers available",
    ):
        async_get_receivers(hass, 433_920_000, ModulationType.OOK)


@pytest.mark.usefixtures("mock_rf_entity", "mock_rf_receiver_entity")
async def test_get_entities_filters_by_type(hass: HomeAssistant) -> None:
    """Test get_transmitters/get_receivers return only entities of matching type."""
    assert async_get_transmitters(hass, 433_920_000, ModulationType.OOK) == [ENTITY_ID]
    assert async_get_receivers(hass, 433_920_000, ModulationType.OOK) == [
        RECEIVER_ENTITY_ID
    ]


@pytest.mark.usefixtures("mock_rf_receiver_entity")
async def test_get_receivers_with_frequency_ranges(hass: HomeAssistant) -> None:
    """Test receiver with frequency ranges filters correctly."""
    result = async_get_receivers(hass, 433_920_000, ModulationType.OOK)
    assert result == [RECEIVER_ENTITY_ID]

    result = async_get_receivers(hass, 868_000_000, ModulationType.OOK)
    assert result == []


@pytest.mark.usefixtures("mock_rf_receiver_entity")
async def test_get_receivers_filters_by_modulation(hass: HomeAssistant) -> None:
    """Test receivers are filtered by supported modulation."""
    result = async_get_receivers(hass, 433_920_000, "no_matching_modulation")  # type: ignore[arg-type]
    assert result == []


@pytest.mark.usefixtures("mock_rf_entity", "mock_rf_receiver_entity")
async def test_rf_entities_initial_state(hass: HomeAssistant) -> None:
    """Test radio frequency entities have no state before any command is sent."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    state = hass.states.get(RECEIVER_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_async_send_command_success(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sending command via async_send_command helper."""
    now = dt_util.utcnow()
    freezer.move_to(now)

    command = MockRadioFrequencyCommand(frequency=433_920_000)
    await async_send_command(hass, ENTITY_ID, command)

    assert len(mock_rf_entity.send_command_calls) == 1
    assert mock_rf_entity.send_command_calls[0].command is command

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == now.isoformat(timespec="milliseconds")


async def test_async_send_command_error_does_not_update_state(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
) -> None:
    """Test that state is not updated when async_send_command raises an error."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    command = MockRadioFrequencyCommand(frequency=433_920_000)

    mock_rf_entity.async_send_command = AsyncMock(
        side_effect=HomeAssistantError("Transmission failed")
    )

    with pytest.raises(HomeAssistantError, match="Transmission failed"):
        await async_send_command(hass, ENTITY_ID, command)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("init_radio_frequency")
async def test_async_send_command_entity_not_found(hass: HomeAssistant) -> None:
    """Test async_send_command raises error when entity not found."""
    command = MockRadioFrequencyCommand(frequency=433_920_000)

    with pytest.raises(
        HomeAssistantError,
        match="Radio Frequency entity `radio_frequency.nonexistent_entity` not found",
    ):
        await async_send_command(hass, "radio_frequency.nonexistent_entity", command)


async def test_async_send_command_rejects_receiver(
    hass: HomeAssistant,
    mock_rf_receiver_entity: MockRadioFrequencyReceiverEntity,
) -> None:
    """Test async_send_command rejects a receiver entity."""
    command = MockRadioFrequencyCommand(frequency=433_920_000)

    with pytest.raises(
        HomeAssistantError,
        match=f"Radio Frequency entity `{RECEIVER_ENTITY_ID}` not found",
    ):
        await async_send_command(hass, RECEIVER_ENTITY_ID, command)


async def test_async_send_command_unsupported_frequency(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
) -> None:
    """Test async_send_command raises when the frequency is not supported."""
    command = MockRadioFrequencyCommand(frequency=868_000_000)

    with pytest.raises(
        HomeAssistantError,
        match=(
            f"Radio Frequency entity `{ENTITY_ID}` "
            "does not support frequency 868000000 Hz"
        ),
    ):
        await async_send_command(hass, ENTITY_ID, command)

    assert mock_rf_entity.send_command_calls == []


@pytest.mark.usefixtures("mock_rf_entity")
async def test_async_send_command_unsupported_modulation(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
) -> None:
    """Test async_send_command raises when the modulation is not supported."""
    command = MockRadioFrequencyCommand(
        frequency=433_920_000,
        modulation="incorrect_modulation",  # type: ignore[arg-type]
    )

    with pytest.raises(
        HomeAssistantError,
        match=(
            f"Radio Frequency entity `{ENTITY_ID}` "
            "does not support modulation incorrect_modulation"
        ),
    ):
        await async_send_command(hass, ENTITY_ID, command)

    assert mock_rf_entity.send_command_calls == []


async def test_async_send_command_component_not_loaded(hass: HomeAssistant) -> None:
    """Test async_send_command raises error when component not loaded."""
    command = MockRadioFrequencyCommand(frequency=433_920_000)

    with pytest.raises(HomeAssistantError, match="component_not_loaded"):
        await async_send_command(hass, "radio_frequency.some_entity", command)


@pytest.mark.parametrize(
    ("restored_value", "expected_state"),
    [
        ("2026-01-01T12:00:00.000+00:00", "2026-01-01T12:00:00.000+00:00"),
        (STATE_UNAVAILABLE, STATE_UNKNOWN),
    ],
)
async def test_rf_entity_state_restore(
    hass: HomeAssistant,
    restored_value: str,
    expected_state: str,
) -> None:
    """Test radio frequency entity state restore."""
    mock_restore_cache(
        hass,
        [State(ENTITY_ID, restored_value), State(RECEIVER_ENTITY_ID, restored_value)],
    )

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities(
        [
            MockRadioFrequencyEntity("test_rf_transmitter"),
            MockRadioFrequencyReceiverEntity("test_rf_receiver"),
        ]
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected_state

    state = hass.states.get(RECEIVER_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


async def test_async_subscribe_receiver_success(
    hass: HomeAssistant,
    mock_rf_receiver_entity: MockRadioFrequencyReceiverEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test subscribing to a receiver via async_subscribe_receiver helper."""
    now = dt_util.utcnow()
    freezer.move_to(now)

    signal_callback = Mock()
    unsubscribe = async_subscribe_receiver(hass, RECEIVER_ENTITY_ID, signal_callback)

    signal = RadioFrequencyReceivedSignal(
        timings=[350, -1050, 350, -350], frequency=433_920_000
    )
    mock_rf_receiver_entity._handle_received_signal(signal)

    assert signal_callback.call_count == 1
    assert signal_callback.call_args[0][0] is signal

    state = hass.states.get(RECEIVER_ENTITY_ID)
    assert state is not None
    assert state.state == now.isoformat(timespec="milliseconds")

    unsubscribe()
    mock_rf_receiver_entity._handle_received_signal(signal)
    assert signal_callback.call_count == 1


async def test_handle_received_signal_isolates_callback_errors(
    hass: HomeAssistant,
    mock_rf_receiver_entity: MockRadioFrequencyReceiverEntity,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failing subscriber does not prevent other subscribers from running."""
    failing_callback = Mock(side_effect=RuntimeError("boom"))
    working_callback = Mock()
    async_subscribe_receiver(hass, RECEIVER_ENTITY_ID, failing_callback)
    async_subscribe_receiver(hass, RECEIVER_ENTITY_ID, working_callback)

    signal = RadioFrequencyReceivedSignal(timings=[350, -1050, 350, -350])
    mock_rf_receiver_entity._handle_received_signal(signal)

    failing_callback.assert_called_once_with(signal)
    working_callback.assert_called_once_with(signal)
    assert "Error in signal callback" in caplog.text


async def test_handle_received_signal_unsubscribe_during_dispatch(
    hass: HomeAssistant,
    mock_rf_receiver_entity: MockRadioFrequencyReceiverEntity,
) -> None:
    """Test a subscriber can unsubscribe itself during dispatch without error."""
    other_callback = Mock()

    def unsubscribing_callback(signal: RadioFrequencyReceivedSignal) -> None:
        unsubscribe()

    self_unsub_mock = Mock(side_effect=unsubscribing_callback)
    unsubscribe = async_subscribe_receiver(hass, RECEIVER_ENTITY_ID, self_unsub_mock)
    async_subscribe_receiver(hass, RECEIVER_ENTITY_ID, other_callback)

    signal = RadioFrequencyReceivedSignal(timings=[350, -1050, 350, -350])
    mock_rf_receiver_entity._handle_received_signal(signal)

    self_unsub_mock.assert_called_once_with(signal)
    other_callback.assert_called_once_with(signal)

    mock_rf_receiver_entity._handle_received_signal(signal)
    self_unsub_mock.assert_called_once_with(signal)
    assert other_callback.call_count == 2


@pytest.mark.usefixtures("init_radio_frequency")
@pytest.mark.parametrize(
    "entity_id_or_uuid",
    ["radio_frequency.nonexistent_entity", "invalid-id"],
)
async def test_async_subscribe_receiver_not_found(
    hass: HomeAssistant, entity_id_or_uuid: str
) -> None:
    """Test async_subscribe_receiver raises when the entity is missing or invalid."""
    with pytest.raises(
        HomeAssistantError,
        match=re.escape(
            f"Radio Frequency receiver entity `{entity_id_or_uuid}` not found"
        ),
    ):
        async_subscribe_receiver(hass, entity_id_or_uuid, lambda _: None)


@pytest.mark.usefixtures("mock_rf_entity")
async def test_async_subscribe_receiver_rejects_transmitter(
    hass: HomeAssistant,
) -> None:
    """Test async_subscribe_receiver rejects a transmitter entity."""
    with pytest.raises(
        HomeAssistantError,
        match=re.escape(f"Radio Frequency receiver entity `{ENTITY_ID}` not found"),
    ):
        async_subscribe_receiver(hass, ENTITY_ID, lambda _: None)


async def test_async_subscribe_receiver_component_not_loaded(
    hass: HomeAssistant,
) -> None:
    """Test async_subscribe_receiver raises error when component not loaded."""
    with pytest.raises(HomeAssistantError, match="component_not_loaded"):
        async_subscribe_receiver(hass, "radio_frequency.some_entity", lambda _: None)


@pytest.mark.usefixtures("init_radio_frequency")
async def test_name(hass: HomeAssistant) -> None:
    """Test entity name / device class naming fallback."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(
            config_entry, [Platform.RADIO_FREQUENCY]
        )

    class MockFlow(ConfigFlow):
        """Test flow."""

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
        ),
    )

    # Unnamed transmitter without has_entity_name -> no name
    transmitter1 = MockRadioFrequencyEntity("test_transmitter1", name=None)
    transmitter1.entity_id = "radio_frequency.test_transmitter1"
    transmitter1._attr_has_entity_name = False

    # Unnamed transmitter with has_entity_name True -> name set from device class
    transmitter2 = MockRadioFrequencyEntity("test_transmitter2", name=None)
    transmitter2.entity_id = "radio_frequency.test_transmitter2"
    transmitter2._attr_has_entity_name = True

    # Unnamed receiver without has_entity_name -> no name
    receiver1 = MockRadioFrequencyReceiverEntity("test_receiver1", name=None)
    receiver1.entity_id = "radio_frequency.test_receiver1"
    receiver1._attr_has_entity_name = False

    # Unnamed receiver with has_entity_name True -> name set from device class
    receiver2 = MockRadioFrequencyReceiverEntity("test_receiver2", name=None)
    receiver2.entity_id = "radio_frequency.test_receiver2"
    receiver2._attr_has_entity_name = True

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Set up test radio frequency platform via config entry."""
        async_add_entities([transmitter1, transmitter2, receiver1, receiver2])

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    with mock_config_flow(TEST_DOMAIN, MockFlow):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state_tx1 = hass.states.get("radio_frequency.test_transmitter1")
    assert state_tx1 is not None
    assert state_tx1.attributes == {"device_class": "transmitter"}

    state_tx2 = hass.states.get("radio_frequency.test_transmitter2")
    assert state_tx2 is not None
    assert state_tx2.attributes == {
        "device_class": "transmitter",
        "friendly_name": "Radio frequency transmitter",
    }

    state_rx1 = hass.states.get("radio_frequency.test_receiver1")
    assert state_rx1 is not None
    assert state_rx1.attributes == {"device_class": "receiver"}

    state_rx2 = hass.states.get("radio_frequency.test_receiver2")
    assert state_rx2 is not None
    assert state_rx2.attributes == {
        "device_class": "receiver",
        "friendly_name": "Radio frequency receiver",
    }
