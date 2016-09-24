"""Test the stress handling of the core."""
import asyncio

import pytest

from homeassistant.bootstrap import setup_component
from homeassistant.util.async import run_coroutine_threadsafe
from tests.common import get_test_home_assistant


@pytest.mark.skipif("os.environ.get('KRAKEN') != 'RELEASE'")
class TestReleaseTheKraken:
    """Test a lot of load on the core."""

    def setup_method(self, method):
        """Setup the test."""
        self.hass = get_test_home_assistant(10)

    def teardown_method(self, method):
        """Clean up."""
        self.hass.stop()

    def test_template_sensor_command_line_sensor_stress(self, caplog):
        """Test many template sensors."""
        batch_size = 40

        sensor_config = {}
        automation_triggers = []
        caplog.set_level('WARNING')
        for i in range(batch_size):
            entity_id = 'kraken.run_%s' % i

            self.hass.states.set(entity_id, 'setup')

            sensor_config['template_{}'.format(i)] = {
                'value_template': 'Hello {{ states.%s.state }}' % entity_id
            }

            automation_triggers.append({
                'platform': 'state',
                'entity_id': entity_id,
            })

        setup_component(self.hass, 'sensor', {
            'sensor': {
                'platform': 'template',
                'sensors': sensor_config
            },
        })
        setup_component(self.hass, 'shell_command', {
            'shell_command': {
                'echo': 'echo 1',
            },
        })
        setup_component(self.hass, 'automation', {
            'automation': {
                'trigger': automation_triggers,
                'action': {
                    'service': 'shell_command.echo',
                },
            },
        })

        self.hass.block_till_done()

        @asyncio.coroutine
        def release(start):
            for i in range(batch_size):
                entity_id = 'kraken.run_{}'.format(i)
                self.hass.states.async_set(entity_id, start + i)

        for i in range(10):
            run_coroutine_threadsafe(
                release(batch_size * i), self.hass.loop).result()

        self.hass.block_till_done()
        assert caplog.text == ''
