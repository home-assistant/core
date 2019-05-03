"""Tests for Minio related helper code."""
import json
from unittest.mock import MagicMock

import homeassistant.components.minio.minio_helper as minio_helper
from tests.components.minio.common import TEST_EVENT


async def test_event_object_iteration(hass):
    """Test iterating over records of Minio event."""
    events = [event for event in minio_helper.iterate_objects(TEST_EVENT)]
    assert 1 == len(events)

    event_name, bucket_name, object_name, metadata = events[0]

    assert 's3:ObjectCreated:Put' == event_name
    assert 'test' == bucket_name
    assert '5jJkTAo.jpg' == object_name
    assert 0 == len(metadata)


async def test_minio_event_stream_iterator(hass):
    """Test event stream iterator over http response."""
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

    assert json.dumps(TEST_EVENT) == json.dumps(event)
