"""Common fixtures for the ADS tests."""

from collections.abc import Callable, Generator
import ctypes
from itertools import count
import threading
from typing import Any, NamedTuple
from unittest.mock import AsyncMock, MagicMock, patch

import pyads
import pytest

from homeassistant.components.ads import hub as ads_hub
from homeassistant.components.ads.const import CONF_LOCAL_NET_ID, DOMAIN
from homeassistant.const import CONF_DEVICE, CONF_IP_ADDRESS, CONF_PORT

from .const import AMS_NET_ID, AUTO_NET_ID, LOCAL_NET_ID

from tests.common import MockConfigEntry


class MockPyadsLocalNetId(NamedTuple):
    """Mocks for the pyads local AMS NetID functions."""

    open_port: MagicMock
    get_local_address: MagicMock
    set_local_address: MagicMock
    close_port: MagicMock


@pytest.fixture(autouse=True)
def _reset_local_net_id_cache() -> None:
    """Ensure the cached original AMS NetID does not leak between tests."""
    ads_hub._original_local_net_id = None


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ads.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_pyads_connection() -> Generator[MagicMock]:
    """Mock the pyads Connection class."""
    with patch("pyads.Connection", autospec=True) as mock_connection:
        yield mock_connection


@pytest.fixture
def mock_pyads_local_net_id() -> Generator[MockPyadsLocalNetId]:
    """Mock the pyads local AMS NetID functions."""
    with (
        patch("pyads.open_port", autospec=True) as mock_open_port,
        patch("pyads.get_local_address", autospec=True) as mock_get_local_address,
        patch("pyads.set_local_address", autospec=True) as mock_set_local_address,
        patch("pyads.close_port", autospec=True) as mock_close_port,
    ):
        mock_get_local_address.return_value.netid = AUTO_NET_ID
        yield MockPyadsLocalNetId(
            mock_open_port,
            mock_get_local_address,
            mock_set_local_address,
            mock_close_port,
        )


def _build_notification(handle: int, payload: bytes) -> Any:
    """Build the notification struct the ADS router hands to a callback."""
    header = pyads.structs.SAdsNotificationHeader
    buffer = (ctypes.c_ubyte * (header.data.offset + len(payload)))()
    notification = ctypes.cast(buffer, ctypes.POINTER(header))
    notification.contents.hNotification = handle
    notification.contents.cbSampleSize = len(payload)
    ctypes.memmove(ctypes.addressof(buffer) + header.data.offset, payload, len(payload))
    return notification


@pytest.fixture
def mock_ads_notifications(
    mock_pyads_connection: MagicMock,
) -> dict[str, bytes]:
    """Push an initial value for every subscription, the way a PLC would.

    Yields a mapping of ADS variable name to the raw bytes to deliver, to be
    filled in before the entities are set up. Variables left out get zeroes.
    """
    values: dict[str, bytes] = {}
    handles = count(1)

    def _add_device_notification(
        name: str,
        attr: pyads.NotificationAttrib,
        callback: Callable[[Any, str], None],
    ) -> tuple[int, int]:
        handle = next(handles)
        payload = values.get(name, b"").ljust(attr.length, b"\x00")
        # The hub registers the handle before releasing the lock the callback
        # takes, so the delivery cannot run ahead of the registration.
        threading.Thread(
            target=callback,
            args=(_build_notification(handle, payload), name),
            daemon=True,
        ).start()
        return handle, handle

    mock_pyads_connection.return_value.add_device_notification.side_effect = (
        _add_device_notification
    )
    return values


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=AMS_NET_ID,
        data={
            CONF_DEVICE: AMS_NET_ID,
            CONF_IP_ADDRESS: "192.168.1.10",
            CONF_PORT: 851,
        },
    )


@pytest.fixture
def mock_config_entry_local_net_id() -> MockConfigEntry:
    """Return a mocked config entry with a custom local AMS NetID."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=AMS_NET_ID,
        data={
            CONF_DEVICE: AMS_NET_ID,
            CONF_IP_ADDRESS: "192.168.1.10",
            CONF_PORT: 851,
            CONF_LOCAL_NET_ID: LOCAL_NET_ID,
        },
    )
