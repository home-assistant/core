"""Tests for Kaleidescape integration."""

from collections.abc import Callable
from unittest.mock import MagicMock

import pytest

from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_SERIAL,
    SsdpServiceInfo,
)

MOCK_HOST = "127.0.0.1"
MOCK_SERIAL = "123456"
MOCK_NAME = "Theater"

MOCK_SSDP_DISCOVERY_INFO = SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="mock_st",
    ssdp_location=f"http://{MOCK_HOST}",
    upnp={
        ATTR_UPNP_FRIENDLY_NAME: MOCK_NAME,
        ATTR_UPNP_SERIAL: MOCK_SERIAL,
    },
)


def find_event_update_callback(
    connect_mock: MagicMock, event_key: str
) -> Callable[..., None]:
    """Find the callback registered for a specific event entity key."""
    for call in connect_mock.call_args_list:
        callback: Callable[..., None] = call[0][0]
        if callback.__closure__ is None:
            continue

        for cell in callback.__closure__:
            if getattr(cell.cell_contents, "entity_description", None) is None:
                continue
            if cell.cell_contents.entity_description.key == event_key:
                return callback

    pytest.fail(f"Callback for event key {event_key} not found")
