"""Utilities for ruuvi_gateway tests."""

from __future__ import annotations

import time
from unittest.mock import _patch, patch

from aioruuvigateway.models import HistoryResponse

from .consts import ASYNC_SETUP_ENTRY, GATEWAY_MAC, GET_GATEWAY_HISTORY_DATA


def patch_gateway_ok() -> _patch:
    """Patch gateway function to return valid data."""
    return patch(
        GET_GATEWAY_HISTORY_DATA,
        return_value=HistoryResponse(
            timestamp=int(time.time()),
            gw_mac=GATEWAY_MAC,
            tags=[],
        ),
    )


def patch_setup_entry_ok() -> _patch:
    """Patch setup entry to return True."""
    return patch(ASYNC_SETUP_ENTRY, return_value=True)
