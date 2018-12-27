"""Tests for the ness_alarm component."""
from enum import Enum

import pytest
from asynctest import patch, MagicMock

from homeassistant.components import alarm_control_panel
from homeassistant.components.ness_alarm import (
    DOMAIN, CONF_DEVICE_PORT, CONF_DEVICE_HOST, CONF_ZONE_NAME, CONF_ZONES,
    CONF_ZONE_ID, SERVICE_AUX, SERVICE_PANIC,
    ATTR_CODE, ATTR_OUTPUT_ID)
from homeassistant.const import (STATE_ALARM_ARMING, SERVICE_ALARM_DISARM,
                                 ATTR_ENTITY_ID, SERVICE_ALARM_ARM_AWAY,
                                 SERVICE_ALARM_ARM_HOME, SERVICE_ALARM_TRIGGER)
from homeassistant.setup import async_setup_component
from tests.common import MockDependency

VALID_CONFIG = {
    DOMAIN: {
        CONF_DEVICE_HOST: 'alarm.local',
        CONF_DEVICE_PORT: 1234,
        CONF_ZONES: [
            {
                CONF_ZONE_NAME: 'Zone 1',
                CONF_ZONE_ID: 1,
            },
            {
                CONF_ZONE_NAME: 'Zone 2',
                CONF_ZONE_ID: 2,
            }
        ]
    }
}


async def test_setup_platform(hass, mock_nessclient):
    """Test platform setup."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    assert hass.services.has_service(DOMAIN, 'panic')
    assert hass.services.has_service(DOMAIN, 'aux')

    await hass.async_block_till_done()
    assert hass.states.get('alarm_control_panel.alarm_panel') is not None
    assert hass.states.get('binary_sensor.zone_1') is not None
    assert hass.states.get('binary_sensor.zone_2') is not None

    mock_nessclient.keepalive.assert_called_once()
    mock_nessclient.update.assert_called_once()


async def test_panic_service(hass, mock_nessclient):
    """Test calling panic service."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.services.async_call(
        DOMAIN, SERVICE_PANIC, blocking=True, service_data={
            ATTR_CODE: '1234'
        })
    mock_nessclient.panic.assert_awaited_once_with('1234')


async def test_aux_service(hass, mock_nessclient):
    """Test calling aux service."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.services.async_call(
        DOMAIN, SERVICE_AUX, blocking=True, service_data={
            ATTR_OUTPUT_ID: 1
        })
    mock_nessclient.aux.assert_awaited_once_with(1, True)


async def test_dispatch_state_change(hass, mock_nessclient):
    """Test calling aux service."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    on_state_change = mock_nessclient.on_state_change.call_args[0][0]
    on_state_change(MockArmingState.ARMING)

    await hass.async_block_till_done()
    assert hass.states.is_state('alarm_control_panel.alarm_panel',
                                STATE_ALARM_ARMING)


async def test_alarm_disarm(hass, mock_nessclient):
    """Test disarm."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    on_state_change = mock_nessclient.on_state_change.call_args[0][0]
    on_state_change(MockArmingState.DISARMED)
    await hass.async_block_till_done()

    await hass.services.async_call(
        alarm_control_panel.DOMAIN, SERVICE_ALARM_DISARM, blocking=True,
        service_data={
            ATTR_ENTITY_ID: 'alarm_control_panel.alarm_panel',
            ATTR_CODE: '1234'
        })
    mock_nessclient.disarm.assert_called_once_with('1234')


async def test_alarm_arm_away(hass, mock_nessclient):
    """Test disarm."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    on_state_change = mock_nessclient.on_state_change.call_args[0][0]
    on_state_change(MockArmingState.DISARMED)
    await hass.async_block_till_done()

    await hass.services.async_call(
        alarm_control_panel.DOMAIN, SERVICE_ALARM_ARM_AWAY, blocking=True,
        service_data={
            ATTR_ENTITY_ID: 'alarm_control_panel.alarm_panel',
            ATTR_CODE: '1234'
        })
    mock_nessclient.arm_away.assert_called_once_with('1234')


async def test_alarm_arm_home(hass, mock_nessclient):
    """Test disarm."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    on_state_change = mock_nessclient.on_state_change.call_args[0][0]
    on_state_change(MockArmingState.DISARMED)
    await hass.async_block_till_done()

    await hass.services.async_call(
        alarm_control_panel.DOMAIN, SERVICE_ALARM_ARM_HOME, blocking=True,
        service_data={
            ATTR_ENTITY_ID: 'alarm_control_panel.alarm_panel',
            ATTR_CODE: '1234'
        })
    mock_nessclient.arm_home.assert_called_once_with('1234')


async def test_alarm_trigger(hass, mock_nessclient):
    """Test disarm."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    on_state_change = mock_nessclient.on_state_change.call_args[0][0]
    on_state_change(MockArmingState.DISARMED)
    await hass.async_block_till_done()

    await hass.services.async_call(
        alarm_control_panel.DOMAIN, SERVICE_ALARM_TRIGGER, blocking=True,
        service_data={
            ATTR_ENTITY_ID: 'alarm_control_panel.alarm_panel',
            ATTR_CODE: '1234'
        })
    mock_nessclient.panic.assert_called_once_with('1234')


async def test_dispatch_zone_change(hass, mock_nessclient):
    """Test zone change events dispatch a signal to subscribers."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    on_zone_change = mock_nessclient.on_zone_change.call_args[0][0]
    on_zone_change(1, True)

    await hass.async_block_till_done()
    assert hass.states.is_state('binary_sensor.zone_1', 'on')


class MockArmingState(Enum):
    """Mock nessclient.ArmingState enum."""

    UNKNOWN = 'UNKNOWN'
    DISARMED = 'DISARMED'
    ARMING = 'ARMING'
    EXIT_DELAY = 'EXIT_DELAY'
    ARMED = 'ARMED'
    ENTRY_DELAY = 'ENTRY_DELAY'
    TRIGGERED = 'TRIGGERED'


class MockClient:
    """Mock nessclient.Client stub."""

    async def panic(self, code):
        """Handle panic."""
        pass

    async def disarm(self, code):
        """Handle disarm."""
        pass

    async def arm_away(self, code):
        """Handle arm_away."""
        pass

    async def arm_home(self, code):
        """Handle arm_home."""
        pass

    async def aux(self, output_id, state):
        """Handle auxiliary control."""
        pass

    async def keepalive(self):
        """Handle keepalive."""
        pass

    async def update(self):
        """Handle update."""
        pass

    def on_zone_change(self):
        """Handle on_zone_change."""
        pass

    def on_state_change(self):
        """Handle on_state_change."""
        pass

    async def close(self):
        """Handle close."""
        pass


@pytest.fixture
def mock_nessclient():
    """Mock the nessclient Client constructor.

    Replaces nessclient.Client with a Mock which always returns the same
    MagicMock() instance.
    """
    _mock_instance = MagicMock(MockClient())
    _mock_factory = MagicMock()
    _mock_factory.return_value = _mock_instance

    with MockDependency('nessclient'), \
        patch('nessclient.Client', new=_mock_factory, create=True), \
            patch('nessclient.ArmingState', new=MockArmingState):
        yield _mock_instance
