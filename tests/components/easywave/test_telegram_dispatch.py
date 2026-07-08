"""Integration tests for Easywave telegram dispatch through config entry setup."""

import asyncio
from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock

from easywave_home_control.codec import (
    ButtonFunction,
    ButtonPushEvent,
    ButtonReleaseEvent,
    MeasurementType,
    SensorTelegramEvent,
)
from easywave_home_control.codec.common import TimerDuration
from easywave_home_control.codec.events import EasywaveButton
from easywave_home_control.codec.sensors import (
    SensorMeasurementPayload,
    SensorPayloadFormat,
)

from homeassistant.components.easywave.const import (
    DOMAIN,
    EVENT_EASYWAVE,
    EVENT_TYPE_BUTTON_PRESS,
    EVENT_TYPE_BUTTON_RELEASE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    MOCK_ENTRY_DATA,
    MOCK_ENTRY_ID,
    MOCK_GATEWAY_TITLE,
    MOCK_NEO_SENSOR_SERIAL,
    MOCK_TRANSMITTER_SERIAL,
    _devices_options,
    _neo_sensor_device_record,
    _transmitter_device_record,
    async_setup_easywave_entry,
    async_stop_easywave_listener,
    mock_easywave_transceiver,
)

from tests.common import MockConfigEntry, async_capture_events

NEO_SENSOR_CAPABILITIES = (1 << 4) | (1 << 5)


async def _setup_entry(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    transceiver: MagicMock,
) -> None:
    """Set up Easywave with a real coordinator and mocked hardware."""
    await async_setup_easywave_entry(hass, entry, transceiver)


async def _teardown_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Stop listener tasks and unload the config entry."""
    await async_stop_easywave_listener(hass, entry)
    if entry.state is ConfigEntryState.LOADED:
        await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def _run_telegram_listener(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    transceiver: MagicMock,
    *telegrams: object,
) -> None:
    """Deliver telegrams through the coordinator listener loop."""
    coordinator = entry.runtime_data.coordinator
    await coordinator.suspend_telegram_listener()

    receive_calls = 0

    async def receive_side_effect(timeout: float = 30.0) -> object:
        nonlocal receive_calls
        receive_calls += 1
        if receive_calls <= len(telegrams):
            return telegrams[receive_calls - 1]
        raise asyncio.CancelledError

    transceiver.receive_telegram = AsyncMock(side_effect=receive_side_effect)
    coordinator.ensure_telegram_listener()
    await hass.async_block_till_done(wait_background_tasks=True)
    await coordinator.suspend_telegram_listener()
    await hass.async_block_till_done()


async def _run_dispatch_test(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    transceiver: MagicMock,
    test_fn: Callable[[], Awaitable[None]],
    *telegrams: object,
) -> None:
    """Run a telegram dispatch test with guaranteed teardown."""
    try:
        await _setup_entry(hass, entry, transceiver)
        await _run_telegram_listener(hass, entry, transceiver, *telegrams)
        await test_fn()
    finally:
        await _teardown_entry(hass, entry)


async def test_button_press_telegram_fires_device_event(
    hass: HomeAssistant,
) -> None:
    """Button push telegrams fire device automation events for known transmitters."""
    transceiver = mock_easywave_transceiver()
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        entry_id=MOCK_ENTRY_ID,
        title=MOCK_GATEWAY_TITLE,
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options=_devices_options(_transmitter_device_record()),
    )
    events = async_capture_events(hass, EVENT_EASYWAVE)

    async def _assert_events() -> None:
        assert any(
            event.data.get("type") == EVENT_TYPE_BUTTON_PRESS
            and event.data.get("subtype") == "a"
            for event in events
        )

    await _run_dispatch_test(
        hass,
        entry,
        transceiver,
        _assert_events,
        ButtonPushEvent(
            transmitter_serial=bytes.fromhex(MOCK_TRANSMITTER_SERIAL),
            button=EasywaveButton.A,
            function=ButtonFunction.DEFAULT,
            should_ignore=False,
        ),
    )


async def test_button_press_low_battery_skips_press_event(
    hass: HomeAssistant,
) -> None:
    """Low-battery telegrams do not fire button press automation events."""
    transceiver = mock_easywave_transceiver()
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        entry_id=MOCK_ENTRY_ID,
        title=MOCK_GATEWAY_TITLE,
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options=_devices_options(_transmitter_device_record()),
    )
    events = async_capture_events(hass, EVENT_EASYWAVE)

    async def _assert_events() -> None:
        assert not any(
            event.data.get("type") == EVENT_TYPE_BUTTON_PRESS for event in events
        )

    await _run_dispatch_test(
        hass,
        entry,
        transceiver,
        _assert_events,
        ButtonPushEvent(
            transmitter_serial=bytes.fromhex(MOCK_TRANSMITTER_SERIAL),
            button=EasywaveButton.A,
            function=ButtonFunction.LOW_BATTERY,
            should_ignore=False,
        ),
    )


async def test_button_press_unknown_transmitter_is_ignored(
    hass: HomeAssistant,
) -> None:
    """Button push telegrams from unknown transmitters are ignored."""
    transceiver = mock_easywave_transceiver()
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        entry_id=MOCK_ENTRY_ID,
        title=MOCK_GATEWAY_TITLE,
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options=_devices_options(_transmitter_device_record()),
    )
    events = async_capture_events(hass, EVENT_EASYWAVE)

    async def _assert_events() -> None:
        assert events == []

    await _run_dispatch_test(
        hass,
        entry,
        transceiver,
        _assert_events,
        ButtonPushEvent(
            transmitter_serial=bytes.fromhex("cc" * 16),
            button=EasywaveButton.B,
            function=ButtonFunction.DEFAULT,
            should_ignore=False,
        ),
    )


async def test_button_release_telegram_fires_device_event(
    hass: HomeAssistant,
) -> None:
    """Button release telegrams fire device automation events."""
    transceiver = mock_easywave_transceiver()
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        entry_id=MOCK_ENTRY_ID,
        title=MOCK_GATEWAY_TITLE,
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options=_devices_options(_transmitter_device_record()),
    )
    events = async_capture_events(hass, EVENT_EASYWAVE)

    async def _assert_events() -> None:
        assert any(
            event.data.get("type") == EVENT_TYPE_BUTTON_RELEASE
            and event.data.get("subtype") == "released"
            for event in events
        )

    await _run_dispatch_test(
        hass,
        entry,
        transceiver,
        _assert_events,
        ButtonReleaseEvent(
            transmitter_serial=bytes.fromhex(MOCK_TRANSMITTER_SERIAL),
        ),
    )


def _temperature_event(serial: str = MOCK_NEO_SENSOR_SERIAL) -> SensorTelegramEvent:
    """Return a temperature measurement telegram."""
    return SensorTelegramEvent(
        sensor_serial=bytes.fromhex(serial),
        payload=SensorMeasurementPayload(
            version=0,
            has_battery=True,
            battery_level=7,
            wire_measurement_type=5,
            measurement_type=MeasurementType.TEMPERATURE,
            payload_format=SensorPayloadFormat.NEO,
            should_ignore=False,
            has_reference=False,
            raw_value=2630,
            reference_value=0,
            max_interval=TimerDuration(mantissa=0, exponent=0, factor_minutes=15.0),
        ),
    )


async def test_neo_sensor_temperature_updates_from_telegram(
    hass: HomeAssistant,
) -> None:
    """Neo sensor measurement telegrams update the temperature entity state."""
    transceiver = mock_easywave_transceiver()
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        entry_id=MOCK_ENTRY_ID,
        title=MOCK_GATEWAY_TITLE,
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options=_devices_options(
            _neo_sensor_device_record(capabilities=NEO_SENSOR_CAPABILITIES)
        ),
    )

    async def _assert_state() -> None:
        entity_id = er.async_get(hass).async_get_entity_id(
            "sensor",
            DOMAIN,
            f"neo_sensor_{MOCK_NEO_SENSOR_SERIAL}_temperature",
        )
        assert entity_id is not None
        assert hass.states.get(entity_id).state == "26.3"

    await _run_dispatch_test(
        hass, entry, transceiver, _assert_state, _temperature_event()
    )


async def test_neo_sensor_temperature_matches_serial_case_insensitively(
    hass: HomeAssistant,
) -> None:
    """Configured neo sensor serials match regardless of hex case."""
    transceiver = mock_easywave_transceiver()
    upper_serial = MOCK_NEO_SENSOR_SERIAL.upper()
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        entry_id=MOCK_ENTRY_ID,
        title=MOCK_GATEWAY_TITLE,
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options=_devices_options(
            _neo_sensor_device_record(
                serial=upper_serial,
                capabilities=NEO_SENSOR_CAPABILITIES,
            )
        ),
    )

    async def _assert_state() -> None:
        entity_id = er.async_get(hass).async_get_entity_id(
            "sensor",
            DOMAIN,
            f"neo_sensor_{upper_serial}_temperature",
        )
        assert entity_id is not None
        assert hass.states.get(entity_id).state == "26.3"

    await _run_dispatch_test(
        hass,
        entry,
        transceiver,
        _assert_state,
        _temperature_event(MOCK_NEO_SENSOR_SERIAL.lower()),
    )
