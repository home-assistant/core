"""Tests for Minio Hass related code."""
import unittest

from tests.common import get_test_home_assistant
import homeassistant.components.minio as minio


class TestMinioHelper(unittest.TestCase):
    """Tests Minio functions."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_queue_listener(self):
        """Tests QueueListener firing events on Hass event bus."""
        queue_listener = minio.QueueListener(self.hass)
        queue_listener.start()

        events = []

        def listener(event):
            events.append(event)

        self.hass.bus.async_listen(minio.DOMAIN, listener)

        queue_entry = {
            "event_name": 's3:ObjectCreated:Put',
            "bucket": 'some_bucket',
            "key": 'some_dir/some_file.jpg',
            "presigned_url": 'http://host/url?signature=secret',
            "metadata": {},
        }

        queue_listener.queue.put(queue_entry)

        self.hass.block_till_done()

        queue_listener.stop()

        self.assertEqual(1, len(events))
        event_data = events[0].data
        self.assertEqual(queue_entry['bucket'], event_data['bucket'])
        self.assertEqual(queue_entry['key'], event_data['key'])
        self.assertEqual(
            queue_entry['presigned_url'], event_data['presigned_url']
        )
        self.assertEqual(queue_entry['event_name'], event_data['event_name'])
        self.assertEqual('some_file.jpg', event_data['file_name'])
        self.assertEqual(0, len(event_data['metadata']))
