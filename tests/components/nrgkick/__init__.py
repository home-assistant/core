"""Tests for the NRGkick integration."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any
from unittest.mock import patch

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def async_setup_entry_with_return(
    hass: HomeAssistant, entry: MockConfigEntry
) -> bool:
    """Set up the component and return boolean success."""
    return await hass.config_entries.async_setup(entry.entry_id)


def create_mock_config_entry(
    domain="nrgkick",
    data=None,
    options=None,
    entry_id="test_entry",
    title="NRGkick",
    unique_id="TEST123456",
):
    """Create a mock config entry for testing."""
    return MockConfigEntry(
        domain=domain,
        data=data or {},
        options=options or {},
        entry_id=entry_id,
        title=title,
        unique_id=unique_id,
    )


@contextmanager
def patch_nrgkickapi(mock_api: Any) -> Generator[patch]:
    """Patch the NRGkickAPI constructor used by the config flow."""

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_api,
    ) as api_cls:
        yield api_cls


__all__ = [
    "async_setup_entry_with_return",
    "create_mock_config_entry",
    "patch_nrgkickapi",
]
