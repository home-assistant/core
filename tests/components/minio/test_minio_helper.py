"""Tests for Minio related helper code"""
import json
import unittest
from unittest.mock import MagicMock

import homeassistant.components.minio.minio_helper as minio_helper
from tests.common import get_test_home_assistant
from tests.components.minio.common import TEST_EVENT


class TestMinioHelper(unittest.TestCase):
    """Tests MinioHelper functions"""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_event_object_iteration(self):
        """Test if message is fired on topic match."""

        events = [event for event in minio_helper.iterate_objects(TEST_EVENT)]
        self.assertEqual(1, len(events))

        event_name, bucket_name, object_name, metadata = events[0]

        self.assertEqual('s3:ObjectCreated:Put', event_name)
        self.assertEqual('test', bucket_name)
        self.assertEqual('5jJkTAo.jpg', object_name)
        self.assertEqual(0, len(metadata))

    def test_MinioEventStreamIterator(self):
        response_mock = MagicMock()
        stream_mock = MagicMock()

        response_mock.stream.return_value = stream_mock

        stream_mock.__next__.side_effect = [
            '',
            '',
            bytearray(json.dumps(TEST_EVENT), 'utf-8')
        ]

        event_it = minio_helper.MinioEventStreamIterator(response_mock)

        event = next(event_it)

        self.assertEqual(json.dumps(TEST_EVENT), json.dumps(event))
        self.assertDictEqual(TEST_EVENT, event)
