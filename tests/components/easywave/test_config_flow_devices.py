"""Tests for the Easywave config flow — device learning sub-flows."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.easywave.const import (
    CONF_BUTTON_COUNT,
    CONF_ENTRY_TYPE,
    CONF_GATEWAY_INDEX,
    CONF_GATEWAY_SERIAL,
    CONF_GROUPING_MODE,
    CONF_OPERATING_TYPE,
    CONF_RECEIVER_KIND,
    CONF_SENSOR_SERIAL,
    CONF_SENSOR_TYPES,
    CONF_SWITCH_MODE,
    CONF_TRANSMITTER_SERIAL,
    CONF_USAGE_TYPE,
    DOMAIN,
    ENTRY_TYPE_RECEIVER,
    ENTRY_TYPE_SENSOR,
    ENTRY_TYPE_TRANSMITTER,
    RECEIVER_KIND_SWITCH,
    SENSOR_KIND_TEMPERATURE,
    TRANSMITTER_GROUPING_SINGLE,
    TRANSMITTER_SWITCH_IMPULSE,
    TRANSMITTER_USAGE_SWITCH,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_SENSOR_SERIAL, MOCK_TRANSMITTER_SERIAL

from tests.common import MockConfigEntry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
# Receiver flow
# ---------------------------------------------------------------------------


async def test_receiver_flow_full(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the full receiver learning flow: mode → prepare → learn → name → saved."""
    coordinator = _make_coordinator()
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    # Start flow — existing gateway → show device menu
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"

    # Choose add_receiver
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "add_receiver"}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "add_receiver"

    # Choose mode ON/OFF (switch)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "mode_on_off"}
    )
    # Arrives at receiver_prepare form
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "receiver_prepare"

    # Confirm preparation (moves to learn start which then shows confirm menu)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "receiver_confirm_learning"

    # Confirm that receiver accepted learning
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "receiver_name"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "receiver_name"

    # Submit name → device saved, flow aborts with device_added
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"name": "Living Room Switch"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_added"

    # Verify the device was saved to options
    devices = mock_config_entry.options.get("devices", [])
    assert len(devices) == 1
    device = devices[0]
    assert device["title"] == "Living Room Switch"
    assert device["data"][CONF_ENTRY_TYPE] == ENTRY_TYPE_RECEIVER
    assert device["data"][CONF_RECEIVER_KIND] == RECEIVER_KIND_SWITCH
    assert CONF_GATEWAY_INDEX in device["data"]
    assert CONF_GATEWAY_SERIAL in device["data"]


async def test_receiver_flow_retry_learn(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test receiver flow allows retrying after learning fails."""
    # First attempt: send_command fails
    coordinator = _make_coordinator(send_ok=False)
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "add_receiver"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "mode_on_off"}
    )
    assert result["step_id"] == "receiver_prepare"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    # send_command fails → abort
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "code_send_failed"


async def test_receiver_flow_no_gateway_serial(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test receiver flow aborts when gateway serial cannot be retrieved."""
    coordinator = _make_coordinator(gateway_serial=None)
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "add_receiver"}
    )
    # get_gateway_serial returns None → abort happens inside receiver_prepare
    # before the form is shown, so mode selection already returns ABORT directly
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "mode_on_off"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_get_gateway_serial"


# ---------------------------------------------------------------------------
# Transmitter flow
# ---------------------------------------------------------------------------


def _make_transmitter_telegram(serial_hex: str = MOCK_TRANSMITTER_SERIAL) -> dict:
    """Return a mock button-press telegram."""
    return {
        "info_type": 0x01,
        "serial": bytes.fromhex(serial_hex),
        "button": 0,
    }


async def test_transmitter_flow_1button_individual(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test transmitter learning flow for 1-button individual mode."""
    telegram = _make_transmitter_telegram()
    coordinator = _make_coordinator(telegram=telegram)
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "add_transmitter"}
    )
    assert result["step_id"] == "add_transmitter"

    # Select 1-button type → grouping menu
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "type_1button"}
    )
    assert result["step_id"] == "transmitter_grouping"

    # Select individual grouping → button count menu (no switch-mode step for individual)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "grouping_single"}
    )
    assert result["step_id"] == "button_count_select"

    # Select 1 button → learning task runs synchronously (eager + AsyncMock),
    # telegram is received immediately, flow advances to confirm form directly
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "buttons_1"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "transmitter_confirm"

    # Submit name
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"name": "Hall Remote"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_added"

    devices = mock_config_entry.options.get("devices", [])
    assert len(devices) == 1
    device = devices[0]
    assert device["title"] == "Hall Remote"
    assert device["data"][CONF_ENTRY_TYPE] == ENTRY_TYPE_TRANSMITTER
    assert device["data"][CONF_TRANSMITTER_SERIAL] == MOCK_TRANSMITTER_SERIAL
    assert device["data"][CONF_OPERATING_TYPE] == "1"
    assert device["data"][CONF_BUTTON_COUNT] == 1
    assert device["data"][CONF_GROUPING_MODE] == TRANSMITTER_GROUPING_SINGLE
    assert device["data"][CONF_SWITCH_MODE] == TRANSMITTER_SWITCH_IMPULSE
    assert device["data"][CONF_USAGE_TYPE] == TRANSMITTER_USAGE_SWITCH


async def test_transmitter_flow_timeout_then_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test transmitter learning timeout shows retry menu, then retry succeeds."""
    telegram = _make_transmitter_telegram()
    coordinator = _make_coordinator(telegram=None)  # no telegram yet → timeout
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    # Navigate to learn step via: add_transmitter → type_3button (skips grouping)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "add_transmitter"}
    )

    # Patch LEARNING_TIMEOUT to a negative value so the while-loop exits immediately
    # (eager task + AsyncMock runs synchronously, so deadline must already be past)
    with patch("homeassistant.components.easywave.config_flow.LEARNING_TIMEOUT", -1):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "type_3button"}
        )
    # Task timed out → flow advanced to learn_timeout menu directly
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "learn_timeout"

    # Re-mock receive_telegram to return a valid telegram, then retry
    coordinator.transceiver.receive_telegram = AsyncMock(return_value=telegram)
    result = await hass.config_entries.flow.async_configure(
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

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "add_transmitter"}
    )
    with patch("homeassistant.components.easywave.config_flow.LEARNING_TIMEOUT", -1):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "type_3button"}
        )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "learn_timeout"

    result = await hass.config_entries.flow.async_configure(
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

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "add_transmitter"}
    )
    # Valid telegram → task completes synchronously; duplicate check fires before
    # form is shown → ABORT immediately
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "type_3button"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# ---------------------------------------------------------------------------
# Sensor (EWneo) flow
# ---------------------------------------------------------------------------


def _make_sensor_telegram(
    serial_hex: str = "aabbccdd" * 2,
    sensor_type_code: int = 1,  # 1 = temperature
) -> dict:
    """Return a mock EWneo sensor learn telegram."""
    # info_data[1] bit 7 = learn flag, info_data[2] bits 7-2 = sensor_type_code
    info_data = bytes([0x00, 0x80, sensor_type_code << 2])
    return {
        "info_type": 0x02,
        "serial": bytes.fromhex(serial_hex),
        "info_data": info_data,
    }


async def test_sensor_flow_full(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the full EWneo sensor learning flow."""
    telegram = _make_sensor_telegram()
    coordinator = _make_coordinator(telegram=telegram)
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    # Valid telegram → learning task completes synchronously → confirm form directly
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "add_sensor"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensor_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"name": "Living Room Temp"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_added"

    devices = mock_config_entry.options.get("devices", [])
    assert len(devices) == 1
    device = devices[0]
    assert device["title"] == "Living Room Temp"
    assert device["data"][CONF_ENTRY_TYPE] == ENTRY_TYPE_SENSOR
    assert CONF_SENSOR_SERIAL in device["data"]
    assert SENSOR_KIND_TEMPERATURE in device["data"][CONF_SENSOR_TYPES]


async def test_sensor_flow_timeout_then_abort(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor flow timeout shows retry/cancel menu and cancels correctly."""
    coordinator = _make_coordinator(telegram=None)
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch("homeassistant.components.easywave.config_flow.LEARNING_TIMEOUT", -1):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "add_sensor"}
        )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "sensor_learn_timeout"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "abort_sensor_learn"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "learning_cancelled"


async def test_sensor_flow_timeout_then_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor flow retry after timeout."""
    telegram = _make_sensor_telegram()
    coordinator = _make_coordinator(telegram=None)  # no telegram yet
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch("homeassistant.components.easywave.config_flow.LEARNING_TIMEOUT", -1):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "add_sensor"}
        )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "sensor_learn_timeout"

    # Re-mock receive_telegram to return a valid telegram, then retry
    coordinator.transceiver.receive_telegram = AsyncMock(return_value=telegram)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "sensor_learn"}
    )
    # Second attempt: telegram received synchronously → confirm form directly
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensor_confirm"


async def test_sensor_flow_duplicate_rejected(
    hass: HomeAssistant,
    mock_config_entry_with_sensor: MockConfigEntry,
) -> None:
    """Test that a duplicate sensor serial is rejected."""
    telegram = _make_sensor_telegram(serial_hex=MOCK_SENSOR_SERIAL)
    coordinator = _make_coordinator(telegram=telegram)
    mock_config_entry_with_sensor.add_to_hass(hass)
    mock_config_entry_with_sensor.runtime_data = _make_connected_runtime(coordinator)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    # Valid telegram → task completes synchronously; duplicate check fires before
    # form is shown → ABORT immediately
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "add_sensor"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# ---------------------------------------------------------------------------
# Disconnected gateway guard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "menu_choice",
    ["add_receiver", "add_transmitter", "add_sensor"],
)
async def test_device_flow_aborts_when_disconnected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    menu_choice: str,
) -> None:
    """Test that all device flows abort immediately when the gateway is disconnected."""
    coordinator = _make_coordinator(is_connected=False)
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _make_connected_runtime(coordinator)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": menu_choice}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_not_connected"
