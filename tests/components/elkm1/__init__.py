"""Tests for the Elk-M1 Control integration."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from elkm1_lib.discovery import ElkSystem

MOCK_IP_ADDRESS = "127.0.0.1"
MOCK_MAC = "aa:bb:cc:dd:ee:ff"
ELK_DISCOVERY = ElkSystem(MOCK_MAC, MOCK_IP_ADDRESS, 2601)
ELK_NON_SECURE_DISCOVERY = ElkSystem(MOCK_MAC, MOCK_IP_ADDRESS, 2101)
ELK_DISCOVERY_NON_STANDARD_PORT = ElkSystem(MOCK_MAC, MOCK_IP_ADDRESS, 444)


def mock_elk(invalid_auth=None, sync_complete=None, exception=None):
    """Mock m1lib Elk."""

    def handler_callbacks(type_, callback):
        nonlocal invalid_auth, sync_complete
        if exception:
            raise exception
        if type_ == "login":
            callback(not invalid_auth)
        elif type_ == "sync_complete" and sync_complete:
            callback()

    mocked_elk = MagicMock()
    mocked_elk.add_handler.side_effect = handler_callbacks
    return mocked_elk


def _patch_discovery(device=None, no_device=False):
    async def _discovery(*args, **kwargs):
        return [] if no_device else [device or ELK_DISCOVERY]

    @contextmanager
    def _patcher():
        with patch(
            "homeassistant.components.elkm1.discovery.AIOELKDiscovery.async_scan",
            new=_discovery,
        ):
            yield

    return _patcher()


def _patch_elk(elk=None):
    def _elk(*args, **kwargs):
        return elk if elk else mock_elk()

    @contextmanager
    def _patcher():
        with patch("homeassistant.components.elkm1.config_flow.Elk", new=_elk,), patch(
            "homeassistant.components.elkm1.config_flow.Elk",
            new=_elk,
        ):
            yield

    return _patcher()
