"""Test rtorrent sensor logging of connection failures."""

from __future__ import annotations

import logging
import xmlrpc.client

import pytest

from homeassistant.components.rtorrent.sensor import (
    SENSOR_TYPE_CURRENT_STATUS,
    SENSOR_TYPES,
    RTorrentSensor,
)

URL_WITH_CREDENTIALS = "https://user:secretpassword@localhost/RPC2"
SECRET = "secretpassword"


class _FailingSystem:
    """Fake xmlrpc system endpoint that fails on every multicall."""

    def multicall(self, calls: list) -> list:
        """Raise a ProtocolError carrying the request URL, like xmlrpc does."""
        raise xmlrpc.client.ProtocolError(URL_WITH_CREDENTIALS, 401, "Unauthorized", {})


class _FailingServer:
    """Fake rtorrent xmlrpc server proxy."""

    def __init__(self) -> None:
        """Initialize the fake server."""
        self.system = _FailingSystem()


def _make_sensor() -> RTorrentSensor:
    """Build an rtorrent sensor backed by a failing server."""
    description = next(
        desc for desc in SENSOR_TYPES if desc.key == SENSOR_TYPE_CURRENT_STATUS
    )
    return RTorrentSensor(_FailingServer(), "rtorrent", description)


def test_connection_failure_does_not_leak_credentials(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ensure the log line for a failed poll never contains the password."""
    caplog.set_level(logging.ERROR)
    sensor = _make_sensor()

    sensor.update()

    assert SECRET not in caplog.text
    assert URL_WITH_CREDENTIALS not in caplog.text
    assert sensor.available is False


def test_connection_failure_still_reports_error_type(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ensure the failure remains diagnosable without leaking credentials."""
    caplog.set_level(logging.ERROR)
    sensor = _make_sensor()

    sensor.update()

    assert "Connection to rtorrent failed (ProtocolError)" in caplog.text
