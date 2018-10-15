"""The tests for the persistent notification component."""
from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.setup import setup_component, async_setup_component
import homeassistant.components.persistent_notification as pn

from tests.common import get_test_home_assistant


class TestPersistentNotification:
    """Test persistent notification component."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        setup_component(self.hass, pn.DOMAIN, {})

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_create(self):
        """Test creating notification without title or notification id."""
        notifications = self.hass.data[pn.DOMAIN]['notifications']
        assert len(self.hass.states.entity_ids(pn.DOMAIN)) == 0
        assert len(notifications) == 0

        pn.create(self.hass, 'Hello World {{ 1 + 1 }}',
                  title='{{ 1 + 1 }} beers')
        self.hass.block_till_done()

        entity_ids = self.hass.states.entity_ids(pn.DOMAIN)
        assert len(entity_ids) == 1
        assert len(notifications) == 1

        state = self.hass.states.get(entity_ids[0])
        assert state.state == pn.STATE
        assert state.attributes.get('message') == 'Hello World 2'
        assert state.attributes.get('title') == '2 beers'

        notification = notifications.get(entity_ids[0])
        assert notification['status'] == pn.STATUS_UNREAD
        assert notification['message'] == 'Hello World 2'
        assert notification['title'] == '2 beers'
        assert notification['created_at'] is not None
        notifications.clear()

    def test_create_notification_id(self):
        """Ensure overwrites existing notification with same id."""
        notifications = self.hass.data[pn.DOMAIN]['notifications']
        assert len(self.hass.states.entity_ids(pn.DOMAIN)) == 0
        assert len(notifications) == 0

        pn.create(self.hass, 'test', notification_id='Beer 2')
        self.hass.block_till_done()

        assert len(self.hass.states.entity_ids()) == 1
        assert len(notifications) == 1

        entity_id = 'persistent_notification.beer_2'
        state = self.hass.states.get(entity_id)
        assert state.attributes.get('message') == 'test'

        notification = notifications.get(entity_id)
        assert notification['message'] == 'test'
        assert notification['title'] is None

        pn.create(self.hass, 'test 2', notification_id='Beer 2')
        self.hass.block_till_done()

        # We should have overwritten old one
        assert len(self.hass.states.entity_ids()) == 1
        state = self.hass.states.get(entity_id)
        assert state.attributes.get('message') == 'test 2'

        notification = notifications.get(entity_id)
        assert notification['message'] == 'test 2'
        notifications.clear()

    def test_create_template_error(self):
        """Ensure we output templates if contain error."""
        notifications = self.hass.data[pn.DOMAIN]['notifications']
        assert len(self.hass.states.entity_ids(pn.DOMAIN)) == 0
        assert len(notifications) == 0

        pn.create(self.hass, '{{ message + 1 }}', '{{ title + 1 }}')
        self.hass.block_till_done()

        entity_ids = self.hass.states.entity_ids(pn.DOMAIN)
        assert len(entity_ids) == 1
        assert len(notifications) == 1

        state = self.hass.states.get(entity_ids[0])
        assert state.attributes.get('message') == '{{ message + 1 }}'
        assert state.attributes.get('title') == '{{ title + 1 }}'

        notification = notifications.get(entity_ids[0])
        assert notification['message'] == '{{ message + 1 }}'
        assert notification['title'] == '{{ title + 1 }}'
        notifications.clear()

    def test_dismiss_notification(self):
        """Ensure removal of specific notification."""
        notifications = self.hass.data[pn.DOMAIN]['notifications']
        assert len(self.hass.states.entity_ids(pn.DOMAIN)) == 0
        assert len(notifications) == 0

        pn.create(self.hass, 'test', notification_id='Beer 2')
        self.hass.block_till_done()

        assert len(self.hass.states.entity_ids(pn.DOMAIN)) == 1
        assert len(notifications) == 1
        pn.dismiss(self.hass, notification_id='Beer 2')
        self.hass.block_till_done()

        assert len(self.hass.states.entity_ids(pn.DOMAIN)) == 0
        assert len(notifications) == 0
        notifications.clear()

    def test_mark_read(self):
        """Ensure notification is marked as Read."""
        notifications = self.hass.data[pn.DOMAIN]['notifications']
        assert len(notifications) == 0

        pn.create(self.hass, 'test', notification_id='Beer 2')
        self.hass.block_till_done()

        entity_id = 'persistent_notification.beer_2'
        assert len(notifications) == 1
        notification = notifications.get(entity_id)
        assert notification['status'] == pn.STATUS_UNREAD

        self.hass.services.call(pn.DOMAIN, pn.SERVICE_MARK_READ, {
            'notification_id': 'Beer 2'
        })
        self.hass.block_till_done()

        assert len(notifications) == 1
        notification = notifications.get(entity_id)
        assert notification['status'] == pn.STATUS_READ
        notifications.clear()


async def test_ws_get_notifications(hass, hass_ws_client):
    """Test websocket endpoint for retrieving persistent notifications."""
    await async_setup_component(hass, pn.DOMAIN, {})

    client = await hass_ws_client(hass)

    await client.send_json({
        'id': 5,
        'type': 'persistent_notification/get'
    })
    msg = await client.receive_json()
    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']
    notifications = msg['result']
    assert len(notifications) == 0

    # Create
    hass.components.persistent_notification.async_create(
        'test', notification_id='Beer 2')
    await client.send_json({
        'id': 6,
        'type': 'persistent_notification/get'
    })
    msg = await client.receive_json()
    assert msg['id'] == 6
    assert msg['type'] == TYPE_RESULT
    assert msg['success']
    notifications = msg['result']
    assert len(notifications) == 1
    notification = notifications[0]
    assert notification['notification_id'] == 'Beer 2'
    assert notification['message'] == 'test'
    assert notification['title'] is None
    assert notification['status'] == pn.STATUS_UNREAD
    assert notification['created_at'] is not None

    # Mark Read
    await hass.services.async_call(pn.DOMAIN, pn.SERVICE_MARK_READ, {
        'notification_id': 'Beer 2'
    })
    await client.send_json({
        'id': 7,
        'type': 'persistent_notification/get'
    })
    msg = await client.receive_json()
    notifications = msg['result']
    assert len(notifications) == 1
    assert notifications[0]['status'] == pn.STATUS_READ

    # Dismiss
    hass.components.persistent_notification.async_dismiss('Beer 2')
    await client.send_json({
        'id': 8,
        'type': 'persistent_notification/get'
    })
    msg = await client.receive_json()
    notifications = msg['result']
    assert len(notifications) == 0
