"""The tests for the Event automation."""
import asyncio
from unittest.mock import patch, Mock

from homeassistant.core import CoreState
from homeassistant.setup import async_setup_component
import homeassistant.components.automation as automation

from tests.common import mock_service, mock_coro


@asyncio.coroutine
def test_if_fires_on_hass_start(hass):
    """Test the firing when HASS starts."""
    calls = mock_service(hass, 'test', 'automation')
    hass.state = CoreState.not_running
    config = {
        automation.DOMAIN: {
            'alias': 'hello',
            'trigger': {
                'platform': 'homeassistant',
                'event': 'start',
            },
            'action': {
                'service': 'test.automation',
            }
        }
    }

    res = yield from async_setup_component(hass, automation.DOMAIN, config)
    assert res
    assert not automation.is_on(hass, 'automation.hello')
    assert len(calls) == 0

    yield from hass.async_start()
    assert automation.is_on(hass, 'automation.hello')
    assert len(calls) == 1

    with patch('homeassistant.config.async_hass_config_yaml',
               Mock(return_value=mock_coro(config))):
        yield from hass.services.async_call(
            automation.DOMAIN, automation.SERVICE_RELOAD, blocking=True)

    assert automation.is_on(hass, 'automation.hello')
    assert len(calls) == 1


@asyncio.coroutine
def test_if_fires_on_hass_shutdown(hass):
    """Test the firing when HASS starts."""
    calls = mock_service(hass, 'test', 'automation')
    hass.state = CoreState.not_running

    res = yield from async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'alias': 'hello',
            'trigger': {
                'platform': 'homeassistant',
                'event': 'shutdown',
            },
            'action': {
                'service': 'test.automation',
            }
        }
    })
    assert res
    assert not automation.is_on(hass, 'automation.hello')
    assert len(calls) == 0

    yield from hass.async_start()
    assert automation.is_on(hass, 'automation.hello')
    assert len(calls) == 0

    with patch.object(hass.loop, 'stop'):
        yield from hass.async_stop()
    assert len(calls) == 1

    # with patch('homeassistant.config.async_hass_config_yaml',
    #            Mock(return_value=mock_coro(config))):
    #     yield from hass.services.async_call(
    #         automation.DOMAIN, automation.SERVICE_RELOAD, blocking=True)

    # assert automation.is_on(hass, 'automation.hello')
    # assert len(calls) == 1
