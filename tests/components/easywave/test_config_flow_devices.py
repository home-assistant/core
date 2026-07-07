"""Tests for the Easywave config flow — device learning sub-flows."""

from unittest.mock import AsyncMock, MagicMock, patch

from easywave_home_control.codec import SensorLearnPayload, SensorTelegramEvent

from homeassistant.components.easywave.const import (
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
    SUBENTRY_DEVICE,
    SUBENTRY_TYPE_NEO_SENSOR,
    SUBENTRY_TYPE_TRANSMITTER,
    TRANSMITTER_GROUPING_GROUP,
    TRANSMITTER_SWITCH_IMPULSE,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_DEVICES
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_TRANSMITTER_SERIAL

from tests.common import MockConfigEntry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _start_transmitter_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> dict:
    """Start the subentry flow for adding a transmitter."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_DEVICE),
        context={"source": SOURCE_USER},
    )
    assert result["step_id"] == "device_select"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": SUBENTRY_TYPE_TRANSMITTER}
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
        (mock_config_entry.entry_id, SUBENTRY_DEVICE),
        context={"source": SOURCE_USER},
    )
    assert result["step_id"] == "device_select"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": SUBENTRY_TYPE_NEO_SENSOR}
    )
    assert result["step_id"] == "sensor_learn_intro"
    return result


async def _start_neo_sensor_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> dict:
    """Start the subentry flow for adding a neo sensor."""
    result = await _start_neo_sensor_flow_until_intro(hass, mock_config_entry)
    return await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "learn"}
    )


_start_device_flow = _start_transmitter_flow


def _make_connected_runtime(coordinator: MagicMock) -> MagicMock:
    """Create a mock runtime_data with a connected coordinator."""
    runtime = MagicMock()
    runtime.coordinator = coordinator
    return runtime


def _make_coordinator(
    *,
    is_connected: bool = True,
    gateway_serial: bytes | None = b"\x00" * 15 + b"\xab",
    send_ok: bool = True,
    telegram: dict | None = None,
) -> MagicMock:
    """Return a mock coordinator with transceiver configured."""
    coordinator = MagicMock()
    coordinator.transceiver.is_connected = is_connected
    coordinator.transceiver.get_gateway_serial = AsyncMock(return_value=gateway_serial)
    coordinator.transceiver.send_command = AsyncMock(return_value=send_ok)
    coordinator.transceiver.receive_telegram = AsyncMock(return_value=telegram)
    coordinator.suspend_telegram_listener = AsyncMock()
    coordinator.resume_telegram_listener = MagicMock()
    return coordinator


# ---------------------------------------------------------------------------
# Transmitter flow
# ---------------------------------------------------------------------------


MOCK_SENSOR_SERIAL = "bb" * 16
NEO_SENSOR_CAPABILITIES = (1 << 4) | (1 << 5)


def _make_transmitter_telegram(serial_hex: str = MOCK_TRANSMITTER_SERIAL) -> dict:
    """Return a mock button-press telegram."""
    return {
        "info_type": 0x01,
        "serial": bytes.fromhex(serial_hex),
        "button": 0,
    }


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
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_added"
    assert result["description_placeholders"] == {"device_name": "Hall Remote"}

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry is not None
    devices = entry.options[CONF_DEVICES]
    assert len(devices) == 1
    device = devices[0]
    assert device["data"][CONF_ENTRY_TYPE] == ENTRY_TYPE_TRANSMITTER
    assert device["data"][CONF_TRANSMITTER_SERIAL] == MOCK_TRANSMITTER_SERIAL
    assert device["data"][CONF_OPERATING_TYPE] == "1"
    assert device["data"][CONF_BUTTON_COUNT] == 4
    assert device["data"][CONF_GROUPING_MODE] == TRANSMITTER_GROUPING_GROUP
    assert device["data"][CONF_SWITCH_MODE] == TRANSMITTER_SWITCH_IMPULSE
    assert device[CONF_DEVICE_TITLE] == "Hall Remote"
    assert not [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == SUBENTRY_DEVICE
    ]


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


# ---------------------------------------------------------------------------
# Neo sensor flow
# ---------------------------------------------------------------------------


async def test_neo_sensor_flow_full(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test neo sensor learning flow: learn → name → saved."""
    telegram = _make_sensor_learn_telegram()
    coordinator = _make_coordinator(telegram=telegram)
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    result = await _start_neo_sensor_flow(hass, mock_config_entry)
    if result["type"] is FlowResultType.SHOW_PROGRESS_DONE:
        result = await hass.config_entries.subentries.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensor_confirm"
    assert (
        result["description_placeholders"]["sensor_list"] == "• Temperature\n• Humidity"
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={"title": "Living Room Sensor"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_added"

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry is not None
    devices = entry.options[CONF_DEVICES]
    assert len(devices) == 1
    device = devices[0]
    assert device["data"][CONF_ENTRY_TYPE] == ENTRY_TYPE_NEO_SENSOR
    assert device["data"][CONF_SENSOR_SERIAL] == MOCK_SENSOR_SERIAL
    assert device["data"][CONF_SENSOR_CAPABILITIES] == NEO_SENSOR_CAPABILITIES
    assert device[CONF_DEVICE_TITLE] == "Living Room Sensor"


async def test_neo_sensor_flow_duplicate_rejected(
    hass: HomeAssistant,
    mock_config_entry_with_neo_sensor: MockConfigEntry,
) -> None:
    """Test that a duplicate neo sensor serial is rejected."""
    telegram = _make_sensor_learn_telegram()
    coordinator = _make_coordinator(telegram=telegram)
    mock_config_entry_with_neo_sensor.add_to_hass(hass)
    mock_config_entry_with_neo_sensor.runtime_data = _make_connected_runtime(
        coordinator
    )

    result = await _start_neo_sensor_flow(hass, mock_config_entry_with_neo_sensor)
    if result["type"] is FlowResultType.SHOW_PROGRESS_DONE:
        result = await hass.config_entries.subentries.async_configure(result["flow_id"])
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
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_added"

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry is not None
    assert entry.options[CONF_DEVICES][0]["data"][CONF_BUTTON_COUNT] == 1


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
        patch(
            "homeassistant.components.easywave.config_flow_learning.EasywaveDeviceFlowMixin._listen_for_telegram",
            side_effect=OSError("serial error"),
        ),
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"next_step_id": "buttons_4"}
        )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "learn_timeout_transmitter"
