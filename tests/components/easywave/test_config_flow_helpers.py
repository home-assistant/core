"""Unit tests for Easywave config flow helper functions."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from easywave_home_control.codec import (
    ButtonFunction,
    ButtonPushEvent,
    SensorTelegramEvent,
)
from easywave_home_control.codec.events import EasywaveButton
import pytest

from homeassistant.components.easywave.config_flow_device import (
    EasywaveDeviceAddFlowMixin,
    _normalize_learned_sensor,
    _normalize_learned_transmitter,
)
from homeassistant.components.easywave.const import (
    ENTRY_TYPE_NEO_SENSOR,
    ENTRY_TYPE_TRANSMITTER,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    MOCK_ENTRY_ID,
    _devices_options,
    _neo_sensor_device_record,
    _transmitter_device_record,
)

from tests.common import MockConfigEntry

MOCK_TRANSMITTER_SERIAL = "aa" * 16
MOCK_SENSOR_SERIAL = "bb" * 16


class _FlowHelper(EasywaveDeviceAddFlowMixin):
    """Minimal flow helper for mixin unit tests."""

    def __init__(self, hass: HomeAssistant, entry: MockConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._init_device_flow()
        self._init_transmitter_flow_state()

    def _get_entry(self) -> MockConfigEntry:
        return self._entry

    def async_abort(
        self,
        *,
        reason: str,
        description_placeholders: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Stub abort for mixin unit tests."""
        return {
            "type": FlowResultType.ABORT,
            "reason": reason,
            "description_placeholders": description_placeholders or {},
        }

    def async_show_progress(self, **kwargs: Any) -> dict[str, Any]:
        """Stub progress step for mixin unit tests."""
        return {"type": FlowResultType.SHOW_PROGRESS, **kwargs}

    def async_show_form(self, **kwargs: Any) -> dict[str, Any]:
        """Stub form step for mixin unit tests."""
        return {"type": FlowResultType.FORM, **kwargs}

    def async_show_menu(self, **kwargs: Any) -> dict[str, Any]:
        """Stub menu step for mixin unit tests."""
        return {"type": FlowResultType.MENU, **kwargs}

    def async_show_progress_done(self, **kwargs: Any) -> dict[str, Any]:
        """Stub progress-done step for mixin unit tests."""
        return {"type": FlowResultType.SHOW_PROGRESS_DONE, **kwargs}


def test_normalize_learned_transmitter_accepts_codec_event() -> None:
    """Transmitter learning accepts ButtonPushEvent telegrams."""
    event = ButtonPushEvent(
        transmitter_serial=bytes.fromhex(MOCK_TRANSMITTER_SERIAL),
        button=EasywaveButton.A,
        function=ButtonFunction.DEFAULT,
        should_ignore=False,
    )

    learned = _normalize_learned_transmitter(event)

    assert learned is not None
    assert learned["serial"] == event.transmitter_serial
    assert learned["button"] == event.button


def test_normalize_learned_transmitter_rejects_invalid_telegram() -> None:
    """Transmitter learning ignores unsupported telegram types."""
    assert _normalize_learned_transmitter({"info_type": 0x01}) is None
    assert _normalize_learned_transmitter(None) is None


def test_normalize_learned_sensor_rejects_invalid_payload() -> None:
    """Neo sensor learning ignores telegrams without learn payloads."""
    event = SensorTelegramEvent(
        sensor_serial=bytes.fromhex(MOCK_SENSOR_SERIAL),
        payload=MagicMock(),
    )

    assert _normalize_learned_sensor(event) is None
    assert _normalize_learned_sensor("invalid") is None


@pytest.mark.parametrize(
    ("entry_type", "serial_hex", "expected"),
    [
        pytest.param(None, MOCK_TRANSMITTER_SERIAL, False, id="missing_entry_type"),
        pytest.param("unsupported", MOCK_TRANSMITTER_SERIAL, False, id="unknown_type"),
    ],
)
def test_is_duplicate_without_matching_serial_key(
    hass: HomeAssistant,
    entry_type: str | None,
    serial_hex: str,
    expected: bool,
) -> None:
    """Duplicate checks without a serial key only match device ids."""
    entry = MockConfigEntry(domain="easywave", subentries_data=())
    entry.add_to_hass(hass)
    helper = _FlowHelper(hass, entry)

    assert (
        helper._is_duplicate(
            "other_device",
            entry_type=entry_type,
            serial_hex=serial_hex,
        )
        is expected
    )


def test_next_default_name_unknown_entry_type(hass: HomeAssistant) -> None:
    """Unknown entry types do not produce a default name."""
    entry = MockConfigEntry(domain="easywave", subentries_data=())
    entry.add_to_hass(hass)
    helper = _FlowHelper(hass, entry)

    assert helper._next_default_name("unsupported") == ""


async def test_listen_for_telegram_skips_unmatched_messages(
    hass: HomeAssistant,
) -> None:
    """Learning keeps listening until a matching telegram arrives."""
    entry = MockConfigEntry(domain="easywave", subentries_data=())
    entry.add_to_hass(hass)
    helper = _FlowHelper(hass, entry)
    coordinator = MagicMock()
    coordinator.suspend_telegram_listener = AsyncMock()
    coordinator.resume_telegram_listener = MagicMock()
    coordinator.transceiver.receive_telegram = AsyncMock(
        side_effect=[
            None,
            ButtonPushEvent(
                transmitter_serial=bytes.fromhex(MOCK_TRANSMITTER_SERIAL),
                button=EasywaveButton.A,
                function=ButtonFunction.DEFAULT,
                should_ignore=False,
            ),
        ]
    )

    with patch(
        "homeassistant.components.easywave.config_flow_learning.LEARNING_TIMEOUT",
        30,
    ):
        learned = await helper._listen_for_telegram(
            coordinator,
            accept_telegram=_normalize_learned_transmitter,
        )

    assert learned is not None
    assert learned["serial"].hex() == MOCK_TRANSMITTER_SERIAL
    assert coordinator.transceiver.receive_telegram.await_count == 2


async def test_await_learning_task_shows_progress(hass: HomeAssistant) -> None:
    """An in-flight learning task shows the progress step."""
    entry = MockConfigEntry(domain="easywave", subentries_data=())
    entry.add_to_hass(hass)
    entry.runtime_data = MagicMock(
        coordinator=MagicMock(transceiver=MagicMock(is_connected=True))
    )
    helper = _FlowHelper(hass, entry)
    helper._learn_progress_action = "waiting_for_transmitter"
    helper._learn_confirm_step = "transmitter_confirm"
    helper._learn_step = "learn_transmitter"
    helper._accept_telegram = _normalize_learned_transmitter

    async def slow_learning(_coordinator: Any) -> dict[str, Any]:
        await asyncio.Future()
        return {}

    helper._learn_task = hass.async_create_task(
        slow_learning(entry.runtime_data.coordinator),
        "easywave_device_learning",
    )

    try:
        result = await helper._await_learning_task(
            progress_action="waiting_for_transmitter",
            confirm_step="transmitter_confirm",
            learn_step="learn_transmitter",
        )

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "learn_transmitter"
    finally:
        helper._learn_task.cancel()


async def test_await_learning_task_aborts_when_disconnected(
    hass: HomeAssistant,
) -> None:
    """Learning aborts when the gateway disconnects before listening."""
    entry = MockConfigEntry(domain="easywave", subentries_data=())
    entry.add_to_hass(hass)
    entry.runtime_data = MagicMock(
        coordinator=MagicMock(transceiver=MagicMock(is_connected=False))
    )
    helper = _FlowHelper(hass, entry)

    result = await helper._await_learning_task(
        progress_action="waiting_for_transmitter",
        confirm_step="transmitter_confirm",
        learn_step="learn_transmitter",
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_not_connected"


async def test_learn_transmitter_and_sensor_steps_delegate(hass: HomeAssistant) -> None:
    """Dedicated learn steps delegate to the shared learn handler."""
    entry = MockConfigEntry(domain="easywave", subentries_data=())
    entry.add_to_hass(hass)
    entry.runtime_data = MagicMock(
        coordinator=MagicMock(transceiver=MagicMock(is_connected=False))
    )
    helper = _FlowHelper(hass, entry)

    transmitter_result = await helper.async_step_learn_transmitter()
    sensor_result = await helper.async_step_learn_sensor()

    assert transmitter_result["type"] is FlowResultType.ABORT
    assert sensor_result["type"] is FlowResultType.ABORT


async def test_transmitter_confirm_aborts_without_learned_device(
    hass: HomeAssistant,
) -> None:
    """Transmitter confirmation aborts when learning did not produce data."""
    entry = MockConfigEntry(domain="easywave", subentries_data=())
    entry.add_to_hass(hass)
    helper = _FlowHelper(hass, entry)
    helper._learned_device = None

    result = await helper.async_step_transmitter_confirm()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_device_learned"


async def test_sensor_confirm_aborts_without_learned_device(
    hass: HomeAssistant,
) -> None:
    """Neo sensor confirmation aborts when learning did not produce data."""
    entry = MockConfigEntry(domain="easywave", subentries_data=())
    entry.add_to_hass(hass)
    helper = _FlowHelper(hass, entry)
    helper._learned_device = None

    result = await helper.async_step_sensor_confirm()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_device_learned"


async def test_neo_sensor_flow_aborts_when_disconnected(hass: HomeAssistant) -> None:
    """Neo sensor setup aborts when the gateway is disconnected."""
    entry = MockConfigEntry(domain="easywave", subentries_data=())
    entry.add_to_hass(hass)
    entry.runtime_data = MagicMock(
        coordinator=MagicMock(transceiver=MagicMock(is_connected=False))
    )
    helper = _FlowHelper(hass, entry)

    result = await helper.async_step_neo_sensor()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_not_connected"


@pytest.mark.parametrize("count_key", ["buttons_2", "buttons_3"])
async def test_transmitter_button_count_steps(
    hass: HomeAssistant,
    count_key: str,
) -> None:
    """Button count menu options set the expected transmitter button count."""
    entry = MockConfigEntry(domain="easywave", subentries_data=())
    entry.add_to_hass(hass)
    entry.runtime_data = MagicMock(
        coordinator=MagicMock(transceiver=MagicMock(is_connected=False))
    )
    helper = _FlowHelper(hass, entry)
    helper._learn_progress_action = "waiting_for_transmitter"
    helper._learn_confirm_step = "transmitter_confirm"
    helper._learn_step = "learn_transmitter"
    helper._accept_telegram = _normalize_learned_transmitter

    step = getattr(helper, f"async_step_{count_key}")
    await step()

    assert helper._button_count == {"buttons_2": 2, "buttons_3": 3}[count_key]


def test_is_duplicate_matches_serial_in_subentries(hass: HomeAssistant) -> None:
    """Duplicate checks match configured transmitter serials."""
    entry = MockConfigEntry(
        domain="easywave",
        entry_id=MOCK_ENTRY_ID,
        options=_devices_options(_transmitter_device_record(title="Other")),
    )
    entry.add_to_hass(hass)
    helper = _FlowHelper(hass, entry)

    assert helper._is_duplicate(
        "transmitter_new",
        entry_type=ENTRY_TYPE_TRANSMITTER,
        serial_hex=MOCK_TRANSMITTER_SERIAL,
    )


def test_is_duplicate_matches_sensor_serial_in_subentries(hass: HomeAssistant) -> None:
    """Duplicate checks match configured neo sensor serials."""
    entry = MockConfigEntry(
        domain="easywave",
        entry_id=MOCK_ENTRY_ID,
        options=_devices_options(_neo_sensor_device_record(title="Other")),
    )
    entry.add_to_hass(hass)
    helper = _FlowHelper(hass, entry)

    assert helper._is_duplicate(
        "neo_sensor_new",
        entry_type=ENTRY_TYPE_NEO_SENSOR,
        serial_hex=MOCK_SENSOR_SERIAL,
    )


def test_is_duplicate_matches_serial_case_insensitively(hass: HomeAssistant) -> None:
    """Duplicate checks ignore hex casing differences."""
    entry = MockConfigEntry(
        domain="easywave",
        entry_id=MOCK_ENTRY_ID,
        options=_devices_options(_transmitter_device_record(title="Other")),
    )
    entry.add_to_hass(hass)
    helper = _FlowHelper(hass, entry)

    assert helper._is_duplicate(
        "transmitter_new",
        entry_type=ENTRY_TYPE_TRANSMITTER,
        serial_hex=MOCK_TRANSMITTER_SERIAL.upper(),
    )
