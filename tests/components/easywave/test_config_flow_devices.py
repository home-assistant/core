"""Tests for the Easywave config flow — device learning sub-flows."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from easywave_home_control.codec import (
    ButtonFunction,
    ButtonPushEvent,
    SensorLearnPayload,
    SensorTelegramEvent,
)
from easywave_home_control.codec.events import EasywaveButton
import pytest

from homeassistant.components.easywave.const import (
    BUCKET_SUBENTRY_TITLES,
    CONF_BUTTON_COUNT,
    CONF_DEVICE_TITLE,
    CONF_ENTRY_TYPE,
    CONF_GROUPING_MODE,
    CONF_OPERATING_TYPE,
    CONF_SENSOR_CAPABILITIES,
    CONF_SENSOR_SERIAL,
    CONF_SWITCH_MODE,
    CONF_TRANSMITTER_SERIAL,
    ENTRY_TYPE_NEO_SENSOR,
    ENTRY_TYPE_TRANSMITTER,
    SUBENTRY_TYPE_EASYWAVE_NEO_SENSOR,
    SUBENTRY_TYPE_EASYWAVE_TRANSMITTER,
    TRANSMITTER_GROUPING_GROUP,
    TRANSMITTER_SWITCH_IMPULSE,
    bucket_subentry_unique_id,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_DEVICES
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    MOCK_TRANSMITTER_SERIAL,
    _entry_with_subentries,
    _transmitter_device_record,
)

from tests.common import MockConfigEntry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _start_transmitter_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> dict:
    """Start the subentry flow for adding a transmitter."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_EASYWAVE_TRANSMITTER),
        context={"source": SOURCE_USER},
    )
    if result["type"] is FlowResultType.ABORT:
        return result
    assert result["step_id"] == "transmitter_learn_intro"
    return await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "button_count_select"}
    )


async def _start_neo_sensor_flow_until_intro(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> dict:
    """Start the neo sensor subentry flow up to the learn intro step."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_EASYWAVE_NEO_SENSOR),
        context={"source": SOURCE_USER},
    )
    assert result["step_id"] == "sensor_learn_intro"
    return result


async def _start_neo_sensor_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> dict:
    """Start the subentry flow for adding a neo sensor."""
    result = await _start_neo_sensor_flow_until_intro(hass, mock_config_entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "learn"}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    await hass.async_block_till_done()
    return await hass.config_entries.subentries.async_configure(result["flow_id"])


_start_device_flow = _start_transmitter_flow


def _make_connected_runtime(coordinator: MagicMock) -> MagicMock:
    """Create a mock runtime_data with a connected coordinator."""
    runtime = MagicMock()
    runtime.coordinator = coordinator
    return runtime


def _make_coordinator(
    *,
    is_connected: bool = True,
    telegram: dict | None = None,
    defer_receive: bool = False,
) -> MagicMock:
    """Return a mock coordinator with transceiver configured."""
    coordinator = MagicMock()
    coordinator.transceiver.is_connected = is_connected
    if defer_receive and telegram is not None:

        async def _receive_telegram(*_args: object, **_kwargs: object) -> object:
            await asyncio.sleep(0)
            return telegram

        coordinator.transceiver.receive_telegram = AsyncMock(
            side_effect=_receive_telegram
        )
    else:
        coordinator.transceiver.receive_telegram = AsyncMock(return_value=telegram)
    coordinator.suspend_telegram_listener = AsyncMock()
    coordinator.resume_telegram_listener = MagicMock()
    return coordinator


# ---------------------------------------------------------------------------
# Transmitter flow
# ---------------------------------------------------------------------------


MOCK_SENSOR_SERIAL = "bb" * 16
NEO_SENSOR_CAPABILITIES = (1 << 4) | (1 << 5)


def _make_transmitter_telegram(
    serial_hex: str = MOCK_TRANSMITTER_SERIAL,
) -> ButtonPushEvent:
    """Return a mock button-press telegram."""
    return ButtonPushEvent(
        transmitter_serial=bytes.fromhex(serial_hex),
        button=EasywaveButton.A,
        function=ButtonFunction.DEFAULT,
        should_ignore=False,
    )


def _make_sensor_learn_telegram(
    serial_hex: str = MOCK_SENSOR_SERIAL,
) -> SensorTelegramEvent:
    """Return a mock neo sensor learn telegram."""
    return SensorTelegramEvent(
        sensor_serial=bytes.fromhex(serial_hex),
        payload=SensorLearnPayload(
            version=0,
            has_battery=True,
            battery_level=7,
            capabilities=NEO_SENSOR_CAPABILITIES,
        ),
    )


async def test_transmitter_flow_group_impulse(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test transmitter learning flow for group-impulse mode (the only supported type)."""
    telegram = _make_transmitter_telegram()
    coordinator = _make_coordinator(telegram=telegram)
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    result = await _start_device_flow(hass, mock_config_entry)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "button_count_select"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "buttons_4"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "transmitter_confirm"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={"title": "Hall Remote"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == BUCKET_SUBENTRY_TITLES[SUBENTRY_TYPE_EASYWAVE_TRANSMITTER]
    assert result["unique_id"] == bucket_subentry_unique_id(
        mock_config_entry.entry_id, SUBENTRY_TYPE_EASYWAVE_TRANSMITTER
    )

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry is not None
    subentries = entry.get_subentries_of_type(SUBENTRY_TYPE_EASYWAVE_TRANSMITTER)
    assert len(subentries) == 1
    subentry = subentries[0]
    device = subentry.data[CONF_DEVICES][f"transmitter_{MOCK_TRANSMITTER_SERIAL}"]
    assert device[CONF_DEVICE_TITLE] == "Hall Remote"
    assert device[CONF_ENTRY_TYPE] == ENTRY_TYPE_TRANSMITTER
    assert device[CONF_TRANSMITTER_SERIAL] == MOCK_TRANSMITTER_SERIAL
    assert device[CONF_OPERATING_TYPE] == "1"
    assert device[CONF_BUTTON_COUNT] == 4
    assert device[CONF_GROUPING_MODE] == TRANSMITTER_GROUPING_GROUP
    assert device[CONF_SWITCH_MODE] == TRANSMITTER_SWITCH_IMPULSE


async def test_transmitter_flow_timeout_then_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test transmitter learning timeout shows retry menu, then retry succeeds."""
    telegram = _make_transmitter_telegram()
    coordinator = _make_coordinator(telegram=None)  # no telegram yet → timeout
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    # Navigate to learn step via: init → button_count_select → buttons_4
    result = await _start_device_flow(hass, mock_config_entry)
    assert result["step_id"] == "button_count_select"

    # Patch LEARNING_TIMEOUT to a negative value so the while-loop exits immediately
    # (eager task + AsyncMock runs synchronously, so deadline must already be past)
    with patch(
        "homeassistant.components.easywave.config_flow_learning.LEARNING_TIMEOUT", -1
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"next_step_id": "buttons_4"}
        )
    # Task timed out → flow advanced to learn_timeout menu directly
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "learn_timeout_transmitter"

    # Re-mock receive_telegram to return a valid telegram, then retry
    coordinator.transceiver.receive_telegram = AsyncMock(return_value=telegram)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "learn"}
    )
    # Second attempt: telegram received synchronously → confirm form directly
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "transmitter_confirm"


async def test_transmitter_flow_abort_learning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that aborting from learn_timeout cancels the flow."""
    coordinator = _make_coordinator(telegram=None)
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    result = await _start_device_flow(hass, mock_config_entry)
    assert result["step_id"] == "button_count_select"
    with patch(
        "homeassistant.components.easywave.config_flow_learning.LEARNING_TIMEOUT", -1
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"next_step_id": "buttons_4"}
        )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "learn_timeout_transmitter"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "abort_learn"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "learning_cancelled"


async def test_transmitter_flow_duplicate_rejected(
    hass: HomeAssistant,
    mock_config_entry_with_transmitter: MockConfigEntry,
) -> None:
    """Test that a duplicate transmitter serial is rejected."""
    telegram = _make_transmitter_telegram()
    coordinator = _make_coordinator(telegram=telegram)
    mock_config_entry_with_transmitter.add_to_hass(hass)
    mock_config_entry_with_transmitter.runtime_data = _make_connected_runtime(
        coordinator
    )

    result = await _start_device_flow(hass, mock_config_entry_with_transmitter)
    assert result["step_id"] == "button_count_select"
    # Valid telegram → duplicate check fires before form is shown → ABORT immediately
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "buttons_4"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_transmitter_flow_adds_second_device_to_existing_bucket(
    hass: HomeAssistant,
    mock_config_entry_with_transmitter: MockConfigEntry,
) -> None:
    """Adding another transmitter updates the existing bucket subentry."""
    second_serial = "cc" * 16
    telegram = _make_transmitter_telegram(serial_hex=second_serial)
    coordinator = _make_coordinator(telegram=telegram)
    mock_config_entry_with_transmitter.add_to_hass(hass)
    mock_config_entry_with_transmitter.runtime_data = _make_connected_runtime(
        coordinator
    )

    result = await _start_device_flow(hass, mock_config_entry_with_transmitter)
    assert result["step_id"] == "button_count_select"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "buttons_4"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "transmitter_confirm"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={"title": "Kitchen Remote"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_added"

    entry = hass.config_entries.async_get_entry(
        mock_config_entry_with_transmitter.entry_id
    )
    assert entry is not None
    subentries = entry.get_subentries_of_type(SUBENTRY_TYPE_EASYWAVE_TRANSMITTER)
    assert len(subentries) == 1
    devices = subentries[0].data[CONF_DEVICES]
    assert len(devices) == 2
    assert f"transmitter_{second_serial}" in devices
    assert (
        devices[f"transmitter_{second_serial}"][CONF_DEVICE_TITLE] == "Kitchen Remote"
    )


# ---------------------------------------------------------------------------
# Neo sensor flow
# ---------------------------------------------------------------------------


async def test_neo_sensor_flow_full(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test neo sensor learning flow: learn → name → saved."""
    telegram = _make_sensor_learn_telegram()
    coordinator = _make_coordinator(telegram=telegram, defer_receive=True)
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    result = await _start_neo_sensor_flow(hass, mock_config_entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensor_confirm"
    assert (
        result["description_placeholders"]["sensor_list"] == "• Temperature\n• Humidity"
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={"title": "Living Room Sensor"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == BUCKET_SUBENTRY_TITLES[SUBENTRY_TYPE_EASYWAVE_NEO_SENSOR]
    assert result["unique_id"] == bucket_subentry_unique_id(
        mock_config_entry.entry_id, SUBENTRY_TYPE_EASYWAVE_NEO_SENSOR
    )

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry is not None
    subentries = entry.get_subentries_of_type(SUBENTRY_TYPE_EASYWAVE_NEO_SENSOR)
    assert len(subentries) == 1
    subentry = subentries[0]
    device = subentry.data[CONF_DEVICES][f"neo_sensor_{MOCK_SENSOR_SERIAL}"]
    assert device[CONF_DEVICE_TITLE] == "Living Room Sensor"
    assert device[CONF_ENTRY_TYPE] == ENTRY_TYPE_NEO_SENSOR
    assert device[CONF_SENSOR_SERIAL] == MOCK_SENSOR_SERIAL
    assert device[CONF_SENSOR_CAPABILITIES] == NEO_SENSOR_CAPABILITIES


async def test_neo_sensor_flow_duplicate_rejected(
    hass: HomeAssistant,
    mock_config_entry_with_neo_sensor: MockConfigEntry,
) -> None:
    """Test that a duplicate neo sensor serial is rejected."""
    telegram = _make_sensor_learn_telegram()
    coordinator = _make_coordinator(telegram=telegram, defer_receive=True)
    mock_config_entry_with_neo_sensor.add_to_hass(hass)
    mock_config_entry_with_neo_sensor.runtime_data = _make_connected_runtime(
        coordinator
    )

    result = await _start_neo_sensor_flow(hass, mock_config_entry_with_neo_sensor)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# ---------------------------------------------------------------------------
# Disconnected gateway guard
# ---------------------------------------------------------------------------


async def test_device_flow_aborts_when_disconnected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the device flow aborts when the gateway is disconnected."""
    coordinator = _make_coordinator(is_connected=False)
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    result = await _start_device_flow(hass, mock_config_entry)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_not_connected"


async def test_device_flow_aborts_without_runtime_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the device flow aborts when the gateway is not set up."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = None

    result = await _start_device_flow(hass, mock_config_entry)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_not_connected"


async def test_transmitter_flow_buttons_1(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test transmitter learning flow with a single button."""
    telegram = _make_transmitter_telegram()
    coordinator = _make_coordinator(telegram=telegram)
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    result = await _start_device_flow(hass, mock_config_entry)
    assert result["step_id"] == "button_count_select"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "buttons_1"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "transmitter_confirm"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={"title": "Single Button Remote"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == BUCKET_SUBENTRY_TITLES[SUBENTRY_TYPE_EASYWAVE_TRANSMITTER]

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry is not None
    assert (
        entry.get_subentries_of_type(SUBENTRY_TYPE_EASYWAVE_TRANSMITTER)[0].data[
            CONF_DEVICES
        ][f"transmitter_{MOCK_TRANSMITTER_SERIAL}"][CONF_BUTTON_COUNT]
        == 1
    )


async def test_neo_sensor_flow_abort_learning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that aborting neo sensor learning from timeout cancels the flow."""
    coordinator = _make_coordinator(telegram=None)
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    result = await _start_neo_sensor_flow_until_intro(hass, mock_config_entry)
    with patch(
        "homeassistant.components.easywave.config_flow_learning.LEARNING_TIMEOUT", -1
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"next_step_id": "learn"}
        )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "learn_timeout_sensor"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "abort_learn"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "learning_cancelled"


async def test_neo_sensor_flow_aborts_when_disconnected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Neo sensor setup aborts when the gateway is disconnected."""
    coordinator = _make_coordinator(is_connected=False)
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_EASYWAVE_NEO_SENSOR),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_not_connected"


async def test_transmitter_flow_duplicate_rejected_case_insensitively(
    hass: HomeAssistant,
) -> None:
    """Duplicate checks ignore transmitter serial hex casing."""
    upper_serial = MOCK_TRANSMITTER_SERIAL.upper()
    configured_entry = _entry_with_subentries(
        _transmitter_device_record(serial=upper_serial, title="Existing Remote")
    )
    configured_entry.add_to_hass(hass)
    coordinator = _make_coordinator(telegram=_make_transmitter_telegram())
    configured_entry.runtime_data = _make_connected_runtime(coordinator)

    result = await _start_device_flow(hass, configured_entry)
    assert result["step_id"] == "button_count_select"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "buttons_4"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_transmitter_flow_skips_unmatched_telegrams(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Transmitter learning keeps listening until a matching telegram arrives."""
    telegram = _make_transmitter_telegram()
    coordinator = _make_coordinator(telegram=None)
    coordinator.transceiver.receive_telegram = AsyncMock(side_effect=[None, telegram])
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    result = await _start_device_flow(hass, mock_config_entry)
    assert result["step_id"] == "button_count_select"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "buttons_4"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "transmitter_confirm"
    assert coordinator.transceiver.receive_telegram.await_count == 2


@pytest.mark.parametrize(
    ("count_key", "expected_count"),
    [
        ("buttons_2", 2),
        ("buttons_3", 3),
    ],
)
async def test_transmitter_flow_button_count_selection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    count_key: str,
    expected_count: int,
) -> None:
    """Button count menu options persist the selected transmitter button count."""
    telegram = _make_transmitter_telegram()
    coordinator = _make_coordinator(telegram=telegram)
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    result = await _start_device_flow(hass, mock_config_entry)
    assert result["step_id"] == "button_count_select"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": count_key}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "transmitter_confirm"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={"title": f"{expected_count}-Button Remote"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry is not None
    devices = entry.get_subentries_of_type(SUBENTRY_TYPE_EASYWAVE_TRANSMITTER)[0].data[
        CONF_DEVICES
    ]
    assert (
        devices[f"transmitter_{MOCK_TRANSMITTER_SERIAL}"][CONF_BUTTON_COUNT]
        == expected_count
    )


async def test_transmitter_flow_with_deferred_telegram(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Transmitter learning shows progress while waiting for a deferred telegram."""
    telegram = _make_transmitter_telegram()
    coordinator = _make_coordinator(telegram=telegram, defer_receive=True)
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    result = await _start_device_flow(hass, mock_config_entry)
    assert result["step_id"] == "button_count_select"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "buttons_4"}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "learn_transmitter"
    await hass.async_block_till_done()
    result = await hass.config_entries.subentries.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "transmitter_confirm"


async def test_neo_sensor_flow_rejects_invalid_learn_telegram(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Neo sensor learning ignores telegrams without learn payloads."""
    invalid_event = SensorTelegramEvent(
        sensor_serial=bytes.fromhex(MOCK_SENSOR_SERIAL),
        payload=MagicMock(),
    )
    coordinator = _make_coordinator(telegram=None)
    coordinator.transceiver.receive_telegram = AsyncMock(return_value=invalid_event)
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    result = await _start_neo_sensor_flow_until_intro(hass, mock_config_entry)
    with patch(
        "homeassistant.components.easywave.config_flow_learning.LEARNING_TIMEOUT",
        0.01,
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"next_step_id": "learn"}
        )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "learn_timeout_sensor"


async def test_transmitter_flow_rejects_invalid_telegram_types(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Transmitter learning ignores unsupported telegram types."""
    invalid_event = SensorTelegramEvent(
        sensor_serial=bytes.fromhex(MOCK_SENSOR_SERIAL),
        payload=MagicMock(),
    )
    coordinator = _make_coordinator(telegram=None)
    coordinator.transceiver.receive_telegram = AsyncMock(return_value=invalid_event)
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    result = await _start_device_flow(hass, mock_config_entry)
    assert result["step_id"] == "button_count_select"
    with patch(
        "homeassistant.components.easywave.config_flow_learning.LEARNING_TIMEOUT",
        0.01,
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"next_step_id": "buttons_4"}
        )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "learn_timeout_transmitter"


async def test_neo_sensor_flow_rejects_non_sensor_telegrams(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Neo sensor learning ignores non-sensor telegrams."""
    invalid_event = _make_transmitter_telegram()
    coordinator = _make_coordinator(telegram=None)
    coordinator.transceiver.receive_telegram = AsyncMock(return_value=invalid_event)
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    result = await _start_neo_sensor_flow_until_intro(hass, mock_config_entry)
    with patch(
        "homeassistant.components.easywave.config_flow_learning.LEARNING_TIMEOUT",
        0.01,
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"next_step_id": "learn"}
        )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "learn_timeout_sensor"


async def test_neo_sensor_learning_aborts_when_gateway_disconnects(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Neo sensor learning aborts if the gateway disconnects before listening."""
    coordinator = _make_coordinator(telegram=None)
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    result = await _start_neo_sensor_flow_until_intro(hass, mock_config_entry)
    with patch(
        "homeassistant.components.easywave.config_flow_learning.LEARNING_TIMEOUT", -1
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"next_step_id": "learn"}
        )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "learn_timeout_sensor"

    coordinator.transceiver.is_connected = False
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "learn"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_not_connected"


async def test_learning_task_oserror_shows_timeout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test OSError during learning is treated as a timeout."""
    coordinator = _make_coordinator(telegram=None)
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    result = await _start_device_flow(hass, mock_config_entry)
    assert result["step_id"] == "button_count_select"

    with (
        patch(
            "homeassistant.components.easywave.config_flow_learning.LEARNING_TIMEOUT",
            30,
        ),
        patch.object(
            coordinator.transceiver,
            "receive_telegram",
            side_effect=OSError("serial error"),
        ),
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"next_step_id": "buttons_4"}
        )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "learn_timeout_transmitter"
