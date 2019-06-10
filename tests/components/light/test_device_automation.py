"""The test for light device automation."""
import pytest

from homeassistant.components import light
from homeassistant.const import (
    STATE_ON, STATE_OFF, CONF_PLATFORM)
from homeassistant.setup import async_setup_component
import homeassistant.components.automation as automation
from homeassistant.components.device_automation import (
    async_get_device_automation_triggers)
from homeassistant.helpers import device_registry


from tests.common import (
    MockConfigEntry, async_mock_service, mock_device_registry, mock_registry)


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


@pytest.fixture
def calls(hass):
    """Track calls to a mock serivce."""
    return async_mock_service(hass, 'test', 'automation')


def _same_triggers(a, b):
    if len(a) != len(b):
        return False

    for d in a:
        if d not in b:
            return False
    return True


async def test_get_triggers(hass, device_reg, entity_reg):
    """Test we get the expected triggers from a light."""
    config_entry = MockConfigEntry(domain='test', data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={
            (device_registry.CONNECTION_NETWORK_MAC, '12:34:56:AB:CD:EF')
        })
    entity_reg.async_get_or_create(
        'light', 'test', '5678', device_id=device_entry.id)
    expected_triggers = [
      {'platform': 'device', 'domain': 'light', 'type': 'turn_off',
       'device_id': device_entry.id, 'entity_id': 'light.test_5678'},
      {'platform': 'device', 'domain': 'light', 'type': 'turn_on',
       'device_id': device_entry.id, 'entity_id': 'light.test_5678'},
    ]
    triggers = await async_get_device_automation_triggers(hass,
                                                          device_entry.id)
    assert _same_triggers(triggers, expected_triggers)


async def test_if_fires_on_state_change(hass, calls):
    """Test for turn_on and turn_off triggers firing."""
    platform = getattr(hass.components, 'test.light')

    platform.init()
    assert await async_setup_component(hass, light.DOMAIN,
                                       {light.DOMAIN: {CONF_PLATFORM: 'test'}})

    dev1, dev2, dev3 = platform.DEVICES

    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: [{
            'trigger': {
                'platform': 'device',
                'domain': light.DOMAIN,
                'entity_id': dev1.entity_id,
                'type':  'turn_on'
            },
            'action': {
                'service': 'test.automation',
                'data_template': {
                    'some':
                        'turn_on {{ trigger.%s }}' % '}} - {{ trigger.'.join((
                            'platform', 'entity_id',
                            'from_state.state', 'to_state.state',
                            'for'))
                },
            }},
            {'trigger': {
                'platform': 'device',
                'domain': light.DOMAIN,
                'entity_id': dev1.entity_id,
                'type':  'turn_off'
            },
            'action': {
                'service': 'test.automation',
                'data_template': {
                    'some':
                        'turn_off {{ trigger.%s }}' % '}} - {{ trigger.'.join((
                            'platform', 'entity_id',
                            'from_state.state', 'to_state.state',
                            'for'))
                },
            }},
        ]
    })
    await hass.async_block_till_done()
    assert hass.states.get(dev1.entity_id).state == STATE_ON
    assert len(calls) == 0

    hass.states.async_set(dev1.entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data['some'] == \
        'turn_off state - {} - on - off - None'.format(dev1.entity_id)

    hass.states.async_set(dev1.entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data['some'] == \
        'turn_on state - {} - off - on - None'.format(dev1.entity_id)
