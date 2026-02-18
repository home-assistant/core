"""Representation of an EnOcean dongle."""

import glob
import logging

from enocean_async.gateway import Gateway

_LOGGER = logging.getLogger(__name__)


def detect():
    """Return a list of candidate paths for USB EnOcean dongles.

    This method is currently a bit simplistic, it may need to be
    improved to support more configurations and OS.
    """
    globs_to_test = [
        "/dev/tty*FTOA2PV*",
        "/dev/serial/by-id/*EnOcean*",
        "/dev/tty.usbserial-*",
    ]
    found_paths = []
    for current_glob in globs_to_test:
        found_paths.extend(glob.glob(current_glob))

    return found_paths


def validate_path(path: str):
    """Return True if the provided path points to a valid serial port, False otherwise."""
    try:
        # Starting the gateway will raise an exception
        # if it cannot connect
        gateway = Gateway(port=path)
        gateway.start()
        gateway.stop()
    except ConnectionError as exception:
        _LOGGER.warning("Dongle path %s is invalid: %s", path, str(exception))
        return False
    return True
