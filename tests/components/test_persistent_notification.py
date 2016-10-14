"""The tests for the persistent notification component."""
from homeassistant.bootstrap import setup_component
import homeassistant.components.persistent_notification as pn

from tests.common import get_test_home_assistant


class TestPersistentNotification:
    """Test persistent notification component."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        setup_component(self.hass, pn.DOMAIN, {})

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_create(self):
        """Test creating notification without title or notification id."""
        assert len(self.hass.states.entity_ids(pn.DOMAIN)) == 0

        pn.create(self.hass, 'Hello World {{ 1 + 1 }}',
                  title='{{ 1 + 1 }} beers')
        self.hass.block_till_done()

        entity_ids = self.hass.states.entity_ids(pn.DOMAIN)
        assert len(entity_ids) == 1

        state = self.hass.states.get(entity_ids[0])
        assert state.state == 'Hello World 2'
        assert state.attributes.get('title') == '2 beers'

    def test_create_notification_id(self):
        """Ensure overwrites existing notification with same id."""
        assert len(self.hass.states.entity_ids(pn.DOMAIN)) == 0

        pn.create(self.hass, 'test', notification_id='Beer 2')
        self.hass.block_till_done()

        assert len(self.hass.states.entity_ids()) == 1
        state = self.hass.states.get('persistent_notification.beer_2')
        assert state.state == 'test'

        pn.create(self.hass, 'test 2', notification_id='Beer 2')
        self.hass.block_till_done()

        # We should have overwritten old one
        assert len(self.hass.states.entity_ids()) == 1
        state = self.hass.states.get('persistent_notification.beer_2')
        assert state.state == 'test 2'

    def test_create_template_error(self):
        """Ensure we output templates if contain error."""
        assert len(self.hass.states.entity_ids(pn.DOMAIN)) == 0

        pn.create(self.hass, '{{ message + 1 }}', '{{ title + 1 }}')
        self.hass.block_till_done()

        entity_ids = self.hass.states.entity_ids(pn.DOMAIN)
        assert len(entity_ids) == 1

        state = self.hass.states.get(entity_ids[0])
        assert state.state == '{{ message + 1 }}'
        assert state.attributes.get('title') == '{{ title + 1 }}'
