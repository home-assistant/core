"""Test the ADS hub."""

import struct
from typing import Any
from unittest.mock import MagicMock

import pyads
import pytest

from homeassistant.components.ads.hub import AdsHub

from . import build_notification


@pytest.fixture
def ads_client() -> MagicMock:
    """Return a mocked pyads client."""
    return MagicMock()


@pytest.fixture
def hub(ads_client: MagicMock) -> AdsHub:
    """Return an AdsHub connected to the mocked client."""
    return AdsHub(ads_client)


def test_write_by_name(hub: AdsHub, ads_client: MagicMock) -> None:
    """Test writing a value by name."""
    hub.write_by_name("GVL.test", 42, pyads.PLCTYPE_INT)

    ads_client.write_by_name.assert_called_once_with("GVL.test", 42, pyads.PLCTYPE_INT)


def test_read_by_name(hub: AdsHub, ads_client: MagicMock) -> None:
    """Test reading a value by name."""
    ads_client.read_by_name.return_value = 42

    assert hub.read_by_name("GVL.test", pyads.PLCTYPE_INT) == 42


@pytest.mark.parametrize(
    ("method", "args"),
    [
        pytest.param("write_by_name", ("GVL.test", 42, pyads.PLCTYPE_INT), id="write"),
        pytest.param("read_by_name", ("GVL.test", pyads.PLCTYPE_INT), id="read"),
    ],
)
def test_io_error_is_logged(
    hub: AdsHub, ads_client: MagicMock, method: str, args: tuple
) -> None:
    """Test an I/O error is logged instead of raised."""
    getattr(ads_client, method).side_effect = pyads.ADSError(text="timeout")

    assert getattr(hub, method)(*args) is None


@pytest.mark.parametrize(
    ("method", "args"),
    [
        pytest.param("write_by_name", ("GVL.test", 42, pyads.PLCTYPE_INT), id="write"),
        pytest.param("read_by_name", ("GVL.test", pyads.PLCTYPE_INT), id="read"),
    ],
)
def test_io_after_shutdown(
    hub: AdsHub, ads_client: MagicMock, method: str, args: tuple
) -> None:
    """Test I/O is refused once the hub is shut down."""
    hub.shutdown()

    assert getattr(hub, method)(*args) is None

    getattr(ads_client, method).assert_not_called()


def test_add_device_notification(hub: AdsHub, ads_client: MagicMock) -> None:
    """Test adding a device notification stores it and returns its handle."""
    ads_client.add_device_notification.return_value = (1, 2)

    assert hub.add_device_notification("GVL.test", pyads.PLCTYPE_INT, MagicMock()) == 1

    assert 1 in hub._notification_items


def test_add_device_notification_error(hub: AdsHub, ads_client: MagicMock) -> None:
    """Test a notification subscription error is logged instead of raised."""
    ads_client.add_device_notification.side_effect = pyads.ADSError(text="timeout")

    assert (
        hub.add_device_notification("GVL.test", pyads.PLCTYPE_INT, MagicMock()) is None
    )

    assert not hub._notification_items


def test_add_device_notification_closed_connection(
    hub: AdsHub, ads_client: MagicMock
) -> None:
    """Test subscribing on a closed connection does not register an item.

    pyads returns None instead of raising once the port is gone.
    """
    ads_client.add_device_notification.return_value = None

    assert (
        hub.add_device_notification("GVL.test", pyads.PLCTYPE_INT, MagicMock()) is None
    )

    assert not hub._notification_items


def test_add_device_notification_after_shutdown(
    hub: AdsHub, ads_client: MagicMock
) -> None:
    """Test a late subscription is refused once the hub is shut down."""
    hub.shutdown()

    assert (
        hub.add_device_notification("GVL.test", pyads.PLCTYPE_INT, MagicMock()) is None
    )

    ads_client.add_device_notification.assert_not_called()
    assert not hub._notification_items


def test_delete_device_notification(hub: AdsHub, ads_client: MagicMock) -> None:
    """Test deleting a single notification drops it from the hub."""
    ads_client.add_device_notification.return_value = (1, 2)
    handle = hub.add_device_notification("GVL.test", pyads.PLCTYPE_INT, MagicMock())

    hub.delete_device_notification(handle)

    ads_client.del_device_notification.assert_called_once_with(1, 2)
    assert not hub._notification_items


def test_delete_device_notification_unknown_handle(
    hub: AdsHub, ads_client: MagicMock
) -> None:
    """Test deleting a notification that shutdown already tore down."""
    hub.delete_device_notification(1)

    ads_client.del_device_notification.assert_not_called()


def test_delete_device_notification_error(hub: AdsHub, ads_client: MagicMock) -> None:
    """Test a deletion error is logged instead of raised."""
    ads_client.add_device_notification.return_value = (1, 2)
    handle = hub.add_device_notification("GVL.test", pyads.PLCTYPE_INT, MagicMock())
    ads_client.del_device_notification.side_effect = pyads.ADSError(text="timeout")

    hub.delete_device_notification(handle)

    assert not hub._notification_items


def test_shutdown(hub: AdsHub, ads_client: MagicMock) -> None:
    """Test shutdown deletes notifications and closes the connection."""
    ads_client.add_device_notification.return_value = (1, 2)
    hub.add_device_notification("GVL.test", pyads.PLCTYPE_INT, MagicMock())

    hub.shutdown()

    ads_client.del_device_notification.assert_called_once_with(1, 2)
    ads_client.close.assert_called_once()
    assert not hub._notification_items


def test_shutdown_ignores_ads_errors(hub: AdsHub, ads_client: MagicMock) -> None:
    """Test shutdown still closes the connection if cleanup calls fail."""
    ads_client.add_device_notification.return_value = (1, 2)
    hub.add_device_notification("GVL.test", pyads.PLCTYPE_INT, MagicMock())
    ads_client.del_device_notification.side_effect = pyads.ADSError(text="timeout")
    ads_client.close.side_effect = pyads.ADSError(text="timeout")

    hub.shutdown()

    assert not hub._notification_items


@pytest.mark.parametrize(
    ("plc_datatype", "payload", "expected"),
    [
        pytest.param(pyads.PLCTYPE_BOOL, b"\x01", True, id="bool"),
        pytest.param(pyads.PLCTYPE_INT, struct.pack("<h", -42), -42, id="int"),
        pytest.param(pyads.PLCTYPE_REAL, struct.pack("<f", 1.5), 1.5, id="real"),
        pytest.param(pyads.PLCTYPE_STRING, b"hello\x00rest", "hello", id="string"),
        pytest.param(
            pyads.PLCTYPE_LINT, b"\x01\x02", bytearray(b"\x01\x02"), id="unsupported"
        ),
    ],
)
def test_notification_is_decoded(
    hub: AdsHub,
    ads_client: MagicMock,
    plc_datatype: type,
    payload: bytes,
    expected: Any,
) -> None:
    """Test an incoming notification is decoded for its PLC data type."""
    ads_client.add_device_notification.return_value = (1, 2)
    notification_callback = MagicMock()
    hub.add_device_notification("GVL.test", plc_datatype, notification_callback)

    # The router calls back into the handler the hub subscribed with.
    handler = ads_client.add_device_notification.call_args.args[2]
    handler(build_notification(1, payload), "GVL.test")

    notification_callback.assert_called_once_with("GVL.test", expected)


def test_notification_for_unknown_handle(
    hub: AdsHub, ads_client: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a notification for a handle the hub does not know is logged."""
    ads_client.add_device_notification.return_value = (1, 2)
    hub.add_device_notification("GVL.test", pyads.PLCTYPE_BOOL, MagicMock())
    handler = ads_client.add_device_notification.call_args.args[2]

    handler(build_notification(99, b"\x01"), "GVL.test")

    assert "Unknown device notification handle: 99" in caplog.text
