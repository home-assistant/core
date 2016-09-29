"""The tests for the Script component."""
# pylint: disable=too-many-public-methods,protected-access
from datetime import timedelta
import unittest

# Otherwise can't test just this file (import order issue)
import homeassistant.components  # noqa
import homeassistant.util.dt as dt_util
from homeassistant.helpers import script, config_validation as cv

from tests.common import fire_time_changed, get_test_home_assistant


ENTITY_ID = 'script.test'


class TestScriptHelper(unittest.TestCase):
    """Test the Script component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_firing_event(self):
        """Test the firing of events."""
        event = 'test_event'
        calls = []

        def record_event(event):
            """Add recorded event to set."""
            calls.append(event)

        self.hass.bus.listen(event, record_event)

        script_obj = script.Script(self.hass, cv.SCRIPT_SCHEMA({
            'event': event,
            'event_data': {
                'hello': 'world'
            }
        }))

        script_obj.run()

        self.hass.block_till_done()

        assert len(calls) == 1
        assert calls[0].data.get('hello') == 'world'
        assert not script_obj.can_cancel

    def test_calling_service(self):
        """Test the calling of a service."""
        calls = []

        def record_call(service):
            """Add recorded event to set."""
            calls.append(service)

        self.hass.services.register('test', 'script', record_call)

        script.call_from_config(self.hass, {
            'service': 'test.script',
            'data': {
                'hello': 'world'
            }
        })

        self.hass.block_till_done()

        assert len(calls) == 1
        assert calls[0].data.get('hello') == 'world'

    def test_calling_service_template(self):
        """Test the calling of a service."""
        calls = []

        def record_call(service):
            """Add recorded event to set."""
            calls.append(service)

        self.hass.services.register('test', 'script', record_call)

        script.call_from_config(self.hass, {
            'service_template': """
                {% if True %}
                    test.script
                {% else %}
                    test.not_script
                {% endif %}""",
            'data_template': {
                'hello': """
                    {% if True %}
                        world
                    {% else %}
                        Not world
                    {% endif %}
                """
            }
        })

        self.hass.block_till_done()

        assert len(calls) == 1
        assert calls[0].data.get('hello') == 'world'

    def test_delay(self):
        """Test the delay."""
        event = 'test_event'
        events = []

        def record_event(event):
            """Add recorded event to set."""
            events.append(event)

        self.hass.bus.listen(event, record_event)

        script_obj = script.Script(self.hass, cv.SCRIPT_SCHEMA([
            {'event': event},
            {'delay': {'seconds': 5}},
            {'event': event}]))

        script_obj.run()

        self.hass.block_till_done()

        assert script_obj.is_running
        assert script_obj.can_cancel
        assert script_obj.last_action == event
        assert len(events) == 1

        future = dt_util.utcnow() + timedelta(seconds=5)
        fire_time_changed(self.hass, future)
        self.hass.block_till_done()

        assert not script_obj.is_running
        assert len(events) == 2

    def test_delay_template(self):
        """Test the delay as a template."""
        event = 'test_evnt'
        events = []

        def record_event(event):
            """Add recorded event to set."""
            events.append(event)

        self.hass.bus.listen(event, record_event)

        script_obj = script.Script(self.hass, cv.SCRIPT_SCHEMA([
            {'event': event},
            {'delay': '00:00:{{ 5 }}'},
            {'event': event}]))

        script_obj.run()

        self.hass.block_till_done()

        assert script_obj.is_running
        assert script_obj.can_cancel
        assert script_obj.last_action == event
        assert len(events) == 1

        future = dt_util.utcnow() + timedelta(seconds=5)
        fire_time_changed(self.hass, future)
        self.hass.block_till_done()

        assert not script_obj.is_running
        assert len(events) == 2

    def test_cancel_while_delay(self):
        """Test the cancelling while the delay is present."""
        event = 'test_event'
        events = []

        def record_event(event):
            """Add recorded event to set."""
            events.append(event)

        self.hass.bus.listen(event, record_event)

        script_obj = script.Script(self.hass, cv.SCRIPT_SCHEMA([
            {'delay': {'seconds': 5}},
            {'event': event}]))

        script_obj.run()

        self.hass.block_till_done()

        assert script_obj.is_running
        assert len(events) == 0

        script_obj.stop()

        assert not script_obj.is_running

        # Make sure the script is really stopped.
        future = dt_util.utcnow() + timedelta(seconds=5)
        fire_time_changed(self.hass, future)
        self.hass.block_till_done()

        assert not script_obj.is_running
        assert len(events) == 0

    def test_passing_variables_to_script(self):
        """Test if we can pass variables to script."""
        calls = []

        def record_call(service):
            """Add recorded event to set."""
            calls.append(service)

        self.hass.services.register('test', 'script', record_call)

        script_obj = script.Script(self.hass, cv.SCRIPT_SCHEMA([
            {
                'service': 'test.script',
                'data_template': {
                    'hello': '{{ greeting }}',
                },
            },
            {'delay': {'seconds': 5}},
            {
                'service': 'test.script',
                'data_template': {
                    'hello': '{{ greeting2 }}',
                },
            }]))

        script_obj.run({
            'greeting': 'world',
            'greeting2': 'universe',
        })

        self.hass.block_till_done()

        assert script_obj.is_running
        assert len(calls) == 1
        assert calls[-1].data['hello'] == 'world'

        future = dt_util.utcnow() + timedelta(seconds=5)
        fire_time_changed(self.hass, future)
        self.hass.block_till_done()

        assert not script_obj.is_running
        assert len(calls) == 2
        assert calls[-1].data['hello'] == 'universe'

    def test_condition(self):
        """Test if we can use conditions in a script."""
        event = 'test_event'
        events = []

        def record_event(event):
            """Add recorded event to set."""
            events.append(event)

        self.hass.bus.listen(event, record_event)

        self.hass.states.set('test.entity', 'hello')

        script_obj = script.Script(self.hass, cv.SCRIPT_SCHEMA([
            {'event': event},
            {
                'condition': 'template',
                'value_template': '{{ states.test.entity.state == "hello" }}',
            },
            {'event': event},
        ]))

        script_obj.run()
        self.hass.block_till_done()
        assert len(events) == 2

        self.hass.states.set('test.entity', 'goodbye')

        script_obj.run()
        self.hass.block_till_done()
        assert len(events) == 3
