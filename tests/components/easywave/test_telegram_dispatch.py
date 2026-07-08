"""Integration tests for Easywave telegram dispatch through config entry setup."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

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
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    MOCK_ENTRY_DATA,
    MOCK_NEO_SENSOR_SERIAL,
    MOCK_TRANSMITTER_SERIAL,
    _devices_options,
    _neo_sensor_device_record,
    _transmitter_device_record,
)

from tests.common import MockConfigEntry, async_capture_events

NEO_SENSOR_CAPABILITIES = (1 << 4) | (1 << 5)


def _mock_transceiver() -> MagicMock:
    """Return a connected transceiver mock for integration tests."""
    transceiver = MagicMock()
    transceiver.is_connected = True
    transceiver.device_path = "/dev/ttyACM0"
    transceiver.usb_serial_number = "12345"
    transceiver.hw_version = "1.0"
    transceiver.fw_version = "2.0"
    transceiver.connect = AsyncMock(return_value=True)
    transceiver.reconnect = AsyncMock(return_value=True)
    transceiver.dispose = AsyncMock()
    transceiver.set_disconnect_callback = MagicMock()
    transceiver.set_connected_callback = MagicMock()
    transceiver.receive_telegram = AsyncMock(return_value=None)
    return transceiver


async def _setup_entry(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    transceiver: MagicMock,
) -> None:
    """Set up Easywave with a real coordinator and mocked hardware."""
    entry.add_to_hass(hass)
    hass.config.country = "DE"
    with patch(
        "homeassistant.components.easywave.RX11Transceiver",
        return_value=transceiver,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _run_telegram_listener(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    transceiver: MagicMock,
    *telegrams: object,
) -> None:
    """Deliver telegrams through the coordinator listener loop."""
    receive_calls = 0

    async def receive_side_effect(timeout: float = 30.0) -> object:
        nonlocal receive_calls
        receive_calls += 1
        if receive_calls <= len(telegrams):
            return telegrams[receive_calls - 1]
        raise asyncio.CancelledError

    transceiver.receive_telegram = AsyncMock(side_effect=receive_side_effect)
    coordinator = entry.runtime_data.coordinator
    coordinator.ensure_telegram_listener()
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_button_press_telegram_fires_device_event(
    hass: HomeAssistant,
) -> None:
    """Button push telegrams fire device automation events for known transmitters."""
    transceiver = _mock_transceiver()
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Easywave Gateway",
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options=_devices_options(_transmitter_device_record()),
    )
    events = async_capture_events(hass, EVENT_EASYWAVE)
    await _setup_entry(hass, entry, transceiver)
    await _run_telegram_listener(
        hass,
        entry,
        transceiver,
        ButtonPushEvent(
            transmitter_serial=bytes.fromhex(MOCK_TRANSMITTER_SERIAL),
            button=EasywaveButton.A,
            function=ButtonFunction.DEFAULT,
            should_ignore=False,
        ),
    )

    assert any(
        event.data.get("type") == EVENT_TYPE_BUTTON_PRESS
        and event.data.get("subtype") == "a"
        for event in events
    )


async def test_button_press_low_battery_skips_press_event(
    hass: HomeAssistant,
) -> None:
    """Low-battery telegrams do not fire button press automation events."""
    transceiver = _mock_transceiver()
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Easywave Gateway",
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options=_devices_options(_transmitter_device_record()),
    )
    events = async_capture_events(hass, EVENT_EASYWAVE)
    await _setup_entry(hass, entry, transceiver)
    await _run_telegram_listener(
        hass,
        entry,
        transceiver,
        ButtonPushEvent(
            transmitter_serial=bytes.fromhex(MOCK_TRANSMITTER_SERIAL),
            button=EasywaveButton.A,
            function=ButtonFunction.LOW_BATTERY,
            should_ignore=False,
        ),
    )

    assert not any(
        event.data.get("type") == EVENT_TYPE_BUTTON_PRESS for event in events
    )


async def test_button_press_unknown_transmitter_is_ignored(
    hass: HomeAssistant,
) -> None:
    """Button push telegrams from unknown transmitters are ignored."""
    transceiver = _mock_transceiver()
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Easywave Gateway",
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options=_devices_options(_transmitter_device_record()),
    )
    events = async_capture_events(hass, EVENT_EASYWAVE)
    await _setup_entry(hass, entry, transceiver)
    await _run_telegram_listener(
        hass,
        entry,
        transceiver,
        ButtonPushEvent(
            transmitter_serial=bytes.fromhex("cc" * 16),
            button=EasywaveButton.B,
            function=ButtonFunction.DEFAULT,
            should_ignore=False,
        ),
    )

    assert events == []


async def test_button_release_telegram_fires_device_event(
    hass: HomeAssistant,
) -> None:
    """Button release telegrams fire device automation events."""
    transceiver = _mock_transceiver()
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Easywave Gateway",
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options=_devices_options(_transmitter_device_record()),
    )
    events = async_capture_events(hass, EVENT_EASYWAVE)
    await _setup_entry(hass, entry, transceiver)
    await _run_telegram_listener(
        hass,
        entry,
        transceiver,
        ButtonReleaseEvent(
            transmitter_serial=bytes.fromhex(MOCK_TRANSMITTER_SERIAL),
        ),
    )

    assert any(
        event.data.get("type") == EVENT_TYPE_BUTTON_RELEASE
        and event.data.get("subtype") == "released"
        for event in events
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
    transceiver = _mock_transceiver()
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Easywave Gateway",
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options=_devices_options(
            _neo_sensor_device_record(capabilities=NEO_SENSOR_CAPABILITIES)
        ),
    )
    await _setup_entry(hass, entry, transceiver)
    await _run_telegram_listener(hass, entry, transceiver, _temperature_event())

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor",
        DOMAIN,
        f"neo_sensor_{MOCK_NEO_SENSOR_SERIAL}_temperature",
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "26.3"


async def test_neo_sensor_temperature_matches_serial_case_insensitively(
    hass: HomeAssistant,
) -> None:
    """Configured neo sensor serials match regardless of hex case."""
    transceiver = _mock_transceiver()
    upper_serial = MOCK_NEO_SENSOR_SERIAL.upper()
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Easywave Gateway",
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
    await _setup_entry(hass, entry, transceiver)
    await _run_telegram_listener(
        hass,
        entry,
        transceiver,
        _temperature_event(MOCK_NEO_SENSOR_SERIAL.lower()),
    )

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor",
        DOMAIN,
        f"neo_sensor_{upper_serial}_temperature",
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "26.3"
