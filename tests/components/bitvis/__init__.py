"""Tests for the Bitvis Power Hub integration."""

from collections.abc import Callable
from unittest.mock import MagicMock

from bitvis_protobuf.listener import FilterMac
from bitvis_protobuf.parse import PayloadDiagnostic, PayloadSample
import pytest

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the integration."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def find_listener_callback(
    mock: MagicMock,
    mac_address: str,
) -> Callable[[PayloadSample | PayloadDiagnostic, tuple[str, int]], None]:
    """Find the listener callback registered for a MAC address."""
    for call in mock.register.call_args_list:
        filt = call[0][0]
        if (
            isinstance(filt, FilterMac)
            and filt.mac_address.lower() == mac_address.lower()
        ):
            return call[0][1]
    pytest.fail(f"Callback for MAC {mac_address} not found")
