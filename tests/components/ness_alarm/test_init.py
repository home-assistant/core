"""Tests for the ness_alarm component."""
from enum import Enum
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components import alarm_control_panel
from homeassistant.components.ness_alarm import (
    ATTR_CODE,
    ATTR_OUTPUT_ID,
    CONF_DEVICE_PORT,
    CONF_ZONE_ID,
    CONF_ZONE_NAME,
    CONF_ZONES,
    DOMAIN,
    SERVICE_AUX,
    SERVICE_PANIC,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

VALID_CONFIG = {
    DOMAIN: {
        CONF_HOST: "alarm.local",
        CONF_DEVICE_PORT: 1234,
        CONF_ZONES: [
            {CONF_ZONE_NAME: "Zone 1", CONF_ZONE_ID: 1},
            {CONF_ZONE_NAME: "Zone 2", CONF_ZONE_ID: 2},
        ],
    }
}


async def test_setup_platform(hass: HomeAssistant, mock_nessclient) -> None:
    """Test platform setup."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    assert hass.services.has_service(DOMAIN, "panic")
    assert hass.services.has_service(DOMAIN, "aux")

    await hass.async_block_till_done()
    assert hass.states.get("alarm_control_panel.alarm_panel") is not None
    assert hass.states.get("binary_sensor.zone_1") is not None
    assert hass.states.get("binary_sensor.zone_2") is not None

    assert mock_nessclient.keepalive.call_count == 1
    assert mock_nessclient.update.call_count == 1


async def test_panic_service(hass: HomeAssistant, mock_nessclient) -> None:
    """Test calling panic service."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.services.async_call(
        DOMAIN, SERVICE_PANIC, blocking=True, service_data={ATTR_CODE: "1234"}
    )
    mock_nessclient.panic.assert_awaited_once_with("1234")


async def test_aux_service(hass: HomeAssistant, mock_nessclient) -> None:
    """Test calling aux service."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.services.async_call(
        DOMAIN, SERVICE_AUX, blocking=True, service_data={ATTR_OUTPUT_ID: 1}
    )
    mock_nessclient.aux.assert_awaited_once_with(1, True)


async def test_dispatch_state_change(hass: HomeAssistant, mock_nessclient) -> None:
    """Test calling aux service."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    on_state_change = mock_nessclient.on_state_change.call_args[0][0]
    on_state_change(MockArmingState.ARMING, None)

    await hass.async_block_till_done()
    assert hass.states.is_state("alarm_control_panel.alarm_panel", STATE_ALARM_ARMING)


async def test_alarm_disarm(hass: HomeAssistant, mock_nessclient) -> None:
    """Test disarm."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    await hass.services.async_call(
        alarm_control_panel.DOMAIN,
        SERVICE_ALARM_DISARM,
        blocking=True,
        service_data={
            ATTR_ENTITY_ID: "alarm_control_panel.alarm_panel",
            ATTR_CODE: "1234",
        },
    )
    mock_nessclient.disarm.assert_called_once_with("1234")


async def test_alarm_arm_away(hass: HomeAssistant, mock_nessclient) -> None:
    """Test disarm."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    await hass.services.async_call(
        alarm_control_panel.DOMAIN,
        SERVICE_ALARM_ARM_AWAY,
        blocking=True,
        service_data={
            ATTR_ENTITY_ID: "alarm_control_panel.alarm_panel",
            ATTR_CODE: "1234",
        },
    )
    mock_nessclient.arm_away.assert_called_once_with("1234")


async def test_alarm_arm_home(hass: HomeAssistant, mock_nessclient) -> None:
    """Test disarm."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    await hass.services.async_call(
        alarm_control_panel.DOMAIN,
        SERVICE_ALARM_ARM_HOME,
        blocking=True,
        service_data={
            ATTR_ENTITY_ID: "alarm_control_panel.alarm_panel",
            ATTR_CODE: "1234",
        },
    )
    mock_nessclient.arm_home.assert_called_once_with("1234")


async def test_alarm_trigger(hass: HomeAssistant, mock_nessclient) -> None:
    """Test disarm."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    await hass.services.async_call(
        alarm_control_panel.DOMAIN,
        SERVICE_ALARM_TRIGGER,
        blocking=True,
        service_data={
            ATTR_ENTITY_ID: "alarm_control_panel.alarm_panel",
            ATTR_CODE: "1234",
        },
    )
    mock_nessclient.panic.assert_called_once_with("1234")


async def test_dispatch_zone_change(hass: HomeAssistant, mock_nessclient) -> None:
    """Test zone change events dispatch a signal to subscribers."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    on_zone_change = mock_nessclient.on_zone_change.call_args[0][0]
    on_zone_change(1, True)

    await hass.async_block_till_done()
    assert hass.states.is_state("binary_sensor.zone_1", "on")
    assert hass.states.is_state("binary_sensor.zone_2", "off")


async def test_arming_state_change(hass: HomeAssistant, mock_nessclient) -> None:
    """Test arming state change handing."""
    states = [
        (MockArmingState.UNKNOWN, None, STATE_UNKNOWN),
        (MockArmingState.DISARMED, None, STATE_ALARM_DISARMED),
        (MockArmingState.ARMING, None, STATE_ALARM_ARMING),
        (MockArmingState.EXIT_DELAY, None, STATE_ALARM_ARMING),
        (MockArmingState.ARMED, None, STATE_ALARM_ARMED_AWAY),
        (MockArmingState.ARMED, MockArmingMode.ARMED_AWAY, STATE_ALARM_ARMED_AWAY),
        (MockArmingState.ARMED, MockArmingMode.ARMED_HOME, STATE_ALARM_ARMED_HOME),
        (MockArmingState.ARMED, MockArmingMode.ARMED_NIGHT, STATE_ALARM_ARMED_NIGHT),
        (MockArmingState.ENTRY_DELAY, None, STATE_ALARM_PENDING),
        (MockArmingState.TRIGGERED, None, STATE_ALARM_TRIGGERED),
    ]

    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()
    assert hass.states.is_state("alarm_control_panel.alarm_panel", STATE_UNKNOWN)
    on_state_change = mock_nessclient.on_state_change.call_args[0][0]

    for arming_state, arming_mode, expected_state in states:
        on_state_change(arming_state, arming_mode)
        await hass.async_block_till_done()
        assert hass.states.is_state("alarm_control_panel.alarm_panel", expected_state)


class MockArmingState(Enum):
    """Mock nessclient.ArmingState enum."""

    UNKNOWN = "UNKNOWN"
    DISARMED = "DISARMED"
    ARMING = "ARMING"
    EXIT_DELAY = "EXIT_DELAY"
    ARMED = "ARMED"
    ENTRY_DELAY = "ENTRY_DELAY"
    TRIGGERED = "TRIGGERED"


class MockArmingMode(Enum):
    """Mock nessclient.ArmingMode enum."""

    ARMED_AWAY = "ARMED_AWAY"
    ARMED_HOME = "ARMED_HOME"
    ARMED_DAY = "ARMED_DAY"
    ARMED_NIGHT = "ARMED_NIGHT"
    ARMED_VACATION = "ARMED_VACATION"
    ARMED_HIGHEST = "ARMED_HIGHEST"


class MockClient:
    """Mock nessclient.Client stub."""

    async def panic(self, code):
        """Handle panic."""

    async def disarm(self, code):
        """Handle disarm."""

    async def arm_away(self, code):
        """Handle arm_away."""

    async def arm_home(self, code):
        """Handle arm_home."""

    async def aux(self, output_id, state):
        """Handle auxiliary control."""

    async def keepalive(self):
        """Handle keepalive."""

    async def update(self):
        """Handle update."""

    def on_zone_change(self):
        """Handle on_zone_change."""

    def on_state_change(self):
        """Handle on_state_change."""

    async def close(self):
        """Handle close."""


@pytest.fixture
def mock_nessclient():
    """Mock the nessclient Client constructor.

    Replaces nessclient.Client with a Mock which always returns the same
    MagicMock() instance.
    """
    _mock_instance = MagicMock(MockClient())
    _mock_factory = MagicMock()
    _mock_factory.return_value = _mock_instance

    with patch(
        "homeassistant.components.ness_alarm.Client", new=_mock_factory, create=True
    ), patch(
        "homeassistant.components.ness_alarm.ArmingState", new=MockArmingState
    ), patch(
        "homeassistant.components.ness_alarm.ArmingMode", new=MockArmingMode
    ), patch(
        "homeassistant.components.ness_alarm.alarm_control_panel.ArmingState",
        new=MockArmingState,
    ), patch(
        "homeassistant.components.ness_alarm.alarm_control_panel.ArmingMode",
        new=MockArmingMode,
    ):
        yield _mock_instance
