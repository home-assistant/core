"""Minio helper methods."""

from __future__ import annotations

from collections.abc import Iterable
import json
import logging
from queue import Queue
import re
import threading
import time
from typing import Self
from urllib.parse import unquote

from minio import Minio
from urllib3.exceptions import HTTPError

_LOGGER = logging.getLogger(__name__)

_METADATA_RE = re.compile("x-amz-meta-(.*)", re.IGNORECASE)


def normalize_metadata(metadata: dict) -> dict:
    """Normalize object metadata by stripping the prefix."""
    new_metadata = {}
    for meta_key, meta_value in metadata.items():
        if not (match := _METADATA_RE.match(meta_key)):
            continue

        new_metadata[match.group(1).lower()] = meta_value

    return new_metadata


def create_minio_client(
    endpoint: str, access_key: str, secret_key: str, secure: bool
) -> Minio:
    """Create Minio client."""
    return Minio(
        endpoint=endpoint, access_key=access_key, secret_key=secret_key, secure=secure
    )


def get_minio_notification_response(
    minio_client, bucket_name: str, prefix: str, suffix: str, events: list[str]
):
    """Start listening to minio events. Copied from minio-py."""
    query = {"prefix": prefix, "suffix": suffix, "events": events}
    return minio_client._url_open(  # noqa: SLF001
        "GET", bucket_name=bucket_name, query=query, preload_content=False
    )


class MinioEventStreamIterator(Iterable):
    """Iterator wrapper over notification http response stream."""

    def __iter__(self) -> Self:
        """Return self."""
        return self

    def __init__(self, response):
        """Init."""
        self._response = response
        self._stream = response.stream()

    def __next__(self):
        """Get next not empty line."""
        while True:
            line = next(self._stream)
            if line.strip():
                event = json.loads(line.decode("utf-8"))
                if event["Records"] is not None:
                    return event

    def close(self):
        """Close the response."""
        self._response.close()


class MinioEventThread(threading.Thread):
    """Thread wrapper around minio notification blocking stream."""

    def __init__(
        self,
        queue: Queue,
        endpoint: str,
        access_key: str,
        secret_key: str,
        secure: bool,
        bucket_name: str,
        prefix: str,
        suffix: str,
        events: list[str],
    ) -> None:
        """Copy over all Minio client options."""
        super().__init__()
        self._queue = queue
        self._endpoint = endpoint
        self._access_key = access_key
        self._secret_key = secret_key
        self._secure = secure
        self._bucket_name = bucket_name
        self._prefix = prefix
        self._suffix = suffix
        self._events = events
        self._event_stream_it = None
        self._should_stop = False

    def __enter__(self):
        """Start the thread."""
        self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop and join the thread."""
        self.stop()

    def run(self):
        """Create MinioClient and run the loop."""
        _LOGGER.debug("Running MinioEventThread")

        self._should_stop = False

        minio_client = create_minio_client(
            self._endpoint, self._access_key, self._secret_key, self._secure
        )

        while not self._should_stop:
            _LOGGER.debug("Connecting to minio event stream")
            response = None
            try:
                response = get_minio_notification_response(
                    minio_client,
                    self._bucket_name,
                    self._prefix,
                    self._suffix,
                    self._events,
                )

                self._event_stream_it = MinioEventStreamIterator(response)

                self._iterate_event_stream(self._event_stream_it, minio_client)
            except json.JSONDecodeError:
                if response:
                    response.close()
            except HTTPError as error:
                _LOGGER.error("Failed to connect to Minio endpoint: %s", error)

                # Wait before attempting to connect again.
                time.sleep(1)
            except AttributeError:
                # When response is closed, iterator will fail to access
                # the underlying socket descriptor.
                break

    def _iterate_event_stream(self, event_stream_it, minio_client):
        for event in event_stream_it:
            for event_name, bucket, key, metadata in iterate_objects(event):
                presigned_url = ""
                try:
                    presigned_url = minio_client.presigned_get_object(bucket, key)
                # Fail gracefully. If for whatever reason this stops working,
                # it shouldn't prevent it from firing events.
                except Exception as error:  # noqa: BLE001
                    _LOGGER.error("Failed to generate presigned url: %s", error)

                queue_entry = {
                    "event_name": event_name,
                    "bucket": bucket,
                    "key": key,
                    "presigned_url": presigned_url,
                    "metadata": metadata,
                }
                _LOGGER.debug("Queue entry, %s", queue_entry)
                self._queue.put(queue_entry)

    def stop(self):
        """Cancel event stream and join the thread."""
        _LOGGER.debug("Stopping event thread")
        self._should_stop = True
        if self._event_stream_it is not None:
            self._event_stream_it.close()
            self._event_stream_it = None

        _LOGGER.debug("Joining event thread")
        self.join()
        _LOGGER.debug("Event thread joined")


def iterate_objects(event):
    """Iterate over file records of notification event.

    Most of the time it should still be only one record.
    """
    records = event.get("Records", [])

    for record in records:
        event_name = record.get("eventName")
        bucket = record.get("s3", {}).get("bucket", {}).get("name")
        key = record.get("s3", {}).get("object", {}).get("key")
        metadata = normalize_metadata(
            record.get("s3", {}).get("object", {}).get("userMetadata", {})
        )

        if not bucket or not key:
            _LOGGER.warning("Invalid bucket and/or key, %s, %s", bucket, key)
            continue

        key = unquote(key)

        yield event_name, bucket, key, metadata
