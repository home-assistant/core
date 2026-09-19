"""Tests for the rtl_433 integration."""

from __future__ import annotations

from unittest.mock import MagicMock

from pyrtl_433.normalizer import NormalizedEvent

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the rtl_433 integration for testing."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def emit_event(
    hass: HomeAssistant, mock_client: MagicMock, event: NormalizedEvent
) -> None:
    """Push a normalized event through the coordinator's ``on_event`` callback.

    The mocked :class:`pyrtl_433.Rtl433Client` never connects to a real server,
    so tests drive the sensor platform by invoking the ``on_event`` callback the
    coordinator registered on the client at construction time.
    """
    on_event = mock_client.call_args.kwargs["on_event"]
    on_event(event)
    await hass.async_block_till_done()
