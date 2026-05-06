"""Tests for the Easywave switch platform."""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.easywave.const import (
    CONF_ENTRY_TYPE,
    CONF_GATEWAY_INDEX,
    CONF_GATEWAY_SERIAL,
    CONF_RECEIVER_KIND,
    DOMAIN,
    ENTRY_TYPE_RECEIVER,
    RECEIVER_KIND_HEATING,
    RECEIVER_KIND_SWITCH,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from .conftest import MOCK_ENTRY_DATA, MOCK_GATEWAY_SERIAL

from tests.common import MockConfigEntry, async_fire_time_changed

MOCK_SUBENTRY_ID = "receiver_subentry_test"


def _get_switch_entity_id(hass: HomeAssistant) -> str:
    """Look up the switch entity_id via unique_id in the entity registry."""
    unique_id = f"{MOCK_SUBENTRY_ID}_switch"
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("switch", DOMAIN, unique_id)
    assert entity_id is not None, f"No switch entity for unique_id {unique_id}"
    return entity_id


def _make_gateway(receiver_kind: str = RECEIVER_KIND_SWITCH) -> MockConfigEntry:
    """Return a gateway entry with a receiver subentry."""
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Easywave Gateway",
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options={
            "devices": [
                {
                    "id": MOCK_SUBENTRY_ID,
                    "title": "Test Receiver",
                    "unique_id": f"receiver_{MOCK_GATEWAY_SERIAL}_0",
                    "data": {
                        CONF_ENTRY_TYPE: ENTRY_TYPE_RECEIVER,
                        CONF_GATEWAY_INDEX: 0,
                        CONF_GATEWAY_SERIAL: MOCK_GATEWAY_SERIAL,
                        CONF_RECEIVER_KIND: receiver_kind,
                    },
                }
            ]
        },
    )


def _patch_integration() -> tuple[Any, Any, Any, Any]:
    """Return patches for transceiver and coordinator."""
    mock_transceiver = MagicMock()
    mock_transceiver.is_connected = True
    mock_transceiver.usb_serial_number = "12345"
    mock_transceiver.hw_version = "1.0"
    mock_transceiver.fw_version = "2.0"
    mock_transceiver.device_path = "/dev/ttyACM0"
    mock_transceiver.send_command = AsyncMock(return_value=True)

    mock_coordinator = MagicMock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()
    mock_coordinator.async_shutdown = AsyncMock()
    mock_coordinator.async_add_listener = MagicMock(return_value=lambda: None)
    mock_coordinator.transceiver = mock_transceiver
    mock_coordinator.is_offline = False
    mock_coordinator.register_transmitter_entities = MagicMock()
    mock_coordinator.data = {"is_connected": True, "device_path": "/dev/ttyACM0"}

    transceiver_patch = patch(
        "homeassistant.components.easywave.RX11Transceiver",
        return_value=mock_transceiver,
    )
    coordinator_patch = patch(
        "homeassistant.components.easywave.EasywaveCoordinator",
        return_value=mock_coordinator,
    )

    return transceiver_patch, coordinator_patch, mock_transceiver, mock_coordinator


async def test_switch_setup(hass: HomeAssistant) -> None:
    """Test switch entity is created from receiver config entry."""
    gateway = _make_gateway()
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    t_patch, c_patch, _mock_transceiver, _mock_coordinator = _patch_integration()
    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(_get_switch_entity_id(hass))
    assert state is not None
    assert state.state == "off"


async def test_switch_turn_on(hass: HomeAssistant) -> None:
    """Test turning on the switch sends button A command."""
    gateway = _make_gateway()
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    t_patch, c_patch, mock_transceiver, _mock_coordinator = _patch_integration()
    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": _get_switch_entity_id(hass)},
            blocking=True,
        )

    mock_transceiver.send_command.assert_called_once_with(
        bytes.fromhex(MOCK_GATEWAY_SERIAL), 0
    )


async def test_switch_turn_off(hass: HomeAssistant) -> None:
    """Test turning off the switch sends button B command."""
    gateway = _make_gateway()
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    t_patch, c_patch, mock_transceiver, _mock_coordinator = _patch_integration()
    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": _get_switch_entity_id(hass)},
            blocking=True,
        )

    mock_transceiver.send_command.assert_called_once_with(
        bytes.fromhex(MOCK_GATEWAY_SERIAL), 1
    )


async def test_switch_unavailable_when_disconnected(hass: HomeAssistant) -> None:
    """Test switch is unavailable when transceiver is disconnected."""
    gateway = _make_gateway()
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    t_patch, c_patch, mock_transceiver, _mock_coordinator = _patch_integration()
    mock_transceiver.is_connected = False

    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(_get_switch_entity_id(hass))
    assert state is not None
    assert state.state == "unavailable"


@pytest.mark.parametrize("restored_state", ["on", "off"])
async def test_heating_restores_state(hass: HomeAssistant, restored_state: str) -> None:
    """Heating switch restores last known on/off state across HA restarts."""
    from homeassistant.components.easywave.switch import (  # noqa: PLC0415
        EasywaveReceiverSwitch,
    )
    from homeassistant.core import State  # noqa: PLC0415

    gateway = _make_gateway(RECEIVER_KIND_HEATING)
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    t_patch, c_patch, _mock_transceiver, _mock_coordinator = _patch_integration()
    with (
        t_patch,
        c_patch,
        patch.object(
            EasywaveReceiverSwitch,
            "async_get_last_state",
            AsyncMock(return_value=State("switch.test", restored_state)),
        ),
    ):
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(_get_switch_entity_id(hass))
    assert state is not None
    assert state.state == restored_state


@pytest.mark.parametrize(
    ("initial_state", "expected_button"),
    [("on", 0), ("off", 1)],
)
async def test_heating_repeats_command_after_interval(
    hass: HomeAssistant,
    initial_state: str,
    expected_button: int,
) -> None:
    """Heating switch resends the current command after 4 h to keep actuator alive."""
    gateway = _make_gateway(RECEIVER_KIND_HEATING)
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    t_patch, c_patch, mock_transceiver, _mock_coordinator = _patch_integration()
    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

        entity_id = _get_switch_entity_id(hass)
        if initial_state == "on":
            await hass.services.async_call(
                "switch", "turn_on", {"entity_id": entity_id}, blocking=True
            )
        mock_transceiver.send_command.reset_mock()

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=4, minutes=1))
        await hass.async_block_till_done()

    mock_transceiver.send_command.assert_called_once_with(
        bytes.fromhex(MOCK_GATEWAY_SERIAL), expected_button
    )


async def test_regular_switch_has_no_repeat_timer(hass: HomeAssistant) -> None:
    """Regular (non-heating) switch must NOT resend commands periodically."""
    gateway = _make_gateway(RECEIVER_KIND_SWITCH)
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    t_patch, c_patch, mock_transceiver, _mock_coordinator = _patch_integration()
    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

        entity_id = _get_switch_entity_id(hass)
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": entity_id}, blocking=True
        )
        mock_transceiver.send_command.reset_mock()

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=4, minutes=1))
        await hass.async_block_till_done()

    mock_transceiver.send_command.assert_not_called()


@pytest.mark.parametrize(
    ("last_sent_offset", "expect_resend"),
    [
        (None, True),  # No previous data → resend
        (timedelta(hours=5), True),  # Last sent 5 h ago → resend
        (timedelta(hours=4), True),  # Exactly 4 h ago → resend (>=)
        (timedelta(hours=1), False),  # Last sent 1 h ago → no resend
    ],
)
async def test_heating_startup_resend_logic(
    hass: HomeAssistant,
    last_sent_offset: timedelta | None,
    expect_resend: bool,
) -> None:
    """Heating switch resends on startup iff last_sent is None or >= 4 h ago."""
    from homeassistant.components.easywave.switch import (  # noqa: PLC0415
        EasywaveReceiverSwitch,
        _SwitchRestoreData,
    )

    gateway = _make_gateway(RECEIVER_KIND_HEATING)
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    now = dt_util.utcnow()
    if last_sent_offset is not None:
        extra_data: _SwitchRestoreData | None = _SwitchRestoreData(
            last_sent=datetime(
                now.year,
                now.month,
                now.day,
                now.hour,
                now.minute,
                now.second,
                tzinfo=UTC,
            )
            - last_sent_offset
        )
    else:
        extra_data = None

    t_patch, c_patch, mock_transceiver, _mock_coordinator = _patch_integration()
    with (
        t_patch,
        c_patch,
        patch.object(
            EasywaveReceiverSwitch,
            "async_get_last_extra_data",
            AsyncMock(return_value=extra_data),
        ),
    ):
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    if expect_resend:
        mock_transceiver.send_command.assert_called()
    else:
        mock_transceiver.send_command.assert_not_called()


async def test_heating_repeat_timer_anchored_to_last_sent(hass: HomeAssistant) -> None:
    """Timer fires at last_sent+4h, not now+4h, so elapsed time is accounted for."""
    from homeassistant.components.easywave.switch import (  # noqa: PLC0415
        EasywaveReceiverSwitch,
        _SwitchRestoreData,
    )

    gateway = _make_gateway(RECEIVER_KIND_HEATING)
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    # Simulate HA was offline for 1 h: last_sent = 1 h ago.
    now = dt_util.utcnow()
    last_sent = now - timedelta(hours=1)
    extra_data = _SwitchRestoreData(last_sent=last_sent)

    t_patch, c_patch, mock_transceiver, _mock_coordinator = _patch_integration()
    with (
        t_patch,
        c_patch,
        patch.object(
            EasywaveReceiverSwitch,
            "async_get_last_extra_data",
            AsyncMock(return_value=extra_data),
        ),
    ):
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

        # No immediate resend (last_sent < 4 h ago).
        mock_transceiver.send_command.assert_not_called()

        # Still no resend just before last_sent + 4 h (now + 2h59m).
        async_fire_time_changed(hass, now + timedelta(hours=2, minutes=59))
        await hass.async_block_till_done()
        mock_transceiver.send_command.assert_not_called()

        # Resend fires at last_sent + 4 h = now + 3 h.
        async_fire_time_changed(hass, now + timedelta(hours=3, minutes=1))
        await hass.async_block_till_done()

    mock_transceiver.send_command.assert_called_once()
