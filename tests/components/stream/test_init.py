"""Test stream init."""

import logging

import av

from homeassistant.components.stream import __name__ as stream_name
from homeassistant.setup import async_setup_component


async def test_log_levels(hass, caplog):
    """Test that the worker logs the url without username and password."""

    logging.getLogger(stream_name).setLevel(logging.INFO)

    await async_setup_component(hass, "stream", {"stream": {}})

    # These namespaces should only pass log messages when the stream logger
    # is at logging.DEBUG or below
    namespaces_to_toggle = (
        "mp4",
        "h264",
        "hevc",
        "rtsp",
        "tcp",
        "tls",
        "mpegts",
        "NULL",
    )

    # Since logging is at INFO, these should not pass
    for namespace in namespaces_to_toggle:
        av.logging.log(av.logging.ERROR, namespace, "SHOULD NOT PASS")

    logging.getLogger(stream_name).setLevel(logging.DEBUG)

    # Since logging is now at DEBUG, these should now pass
    for namespace in namespaces_to_toggle:
        av.logging.log(av.logging.ERROR, namespace, "SHOULD PASS")

    # Even though logging is at DEBUG, these should not pass
    av.logging.log(av.logging.WARNING, "mp4", "SHOULD NOT PASS")
    av.logging.log(av.logging.WARNING, "swscaler", "SHOULD NOT PASS")

    assert "SHOULD PASS" in caplog.text
    assert "SHOULD NOT PASS" not in caplog.text
