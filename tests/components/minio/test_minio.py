"""Tests for Minio Hass related code."""
import homeassistant.core as ha
import homeassistant.components.minio as minio


async def test_queue_listener(hass):
    """Tests QueueListener firing events on Hass event bus."""
    queue_listener = minio.QueueListener(hass)
    queue_listener.start()

    events = []

    @ha.callback
    def listener(event):
        print("FUCK")
        events.append(event)

    hass.bus.async_listen(minio.DOMAIN, listener)

    queue_entry = {
        "event_name": 's3:ObjectCreated:Put',
        "bucket": 'some_bucket',
        "key": 'some_dir/some_file.jpg',
        "presigned_url": 'http://host/url?signature=secret',
        "metadata": {},
    }

    queue_listener.queue.put(queue_entry)

    await hass.async_block_till_done()

    queue_listener.stop()

    await hass.async_block_till_done()

    assert 1 == len(events)
    event_data = events[0].data
    assert queue_entry['bucket'] == event_data['bucket']
    assert queue_entry['key'] == event_data['key']
    assert queue_entry['presigned_url'] == event_data['presigned_url']

    assert queue_entry['event_name'] == event_data['event_name']
    assert 'some_file.jpg' == event_data['file_name']
    assert 0 == len(event_data['metadata'])
