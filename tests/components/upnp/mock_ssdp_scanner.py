"""Mock ssdp.Scanner."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components import ssdp
from homeassistant.core import callback


class MockSsdpDescriptionManager(ssdp.DescriptionManager):
    """Mocked ssdp DescriptionManager."""

    async def fetch_description(
        self, xml_location: str | None
    ) -> None | dict[str, str]:
        """Fetch the location or get it from the cache."""
        if xml_location is None:
            return None
        return {}


class MockSsdpScanner(ssdp.Scanner):
    """Mocked ssdp Scanner."""

    @callback
    def async_stop(self, *_: Any) -> None:
        """Stop the scanner."""
        # Do nothing.

    async def async_start(self) -> None:
        """Start the scanner."""
        self.description_manager = MockSsdpDescriptionManager(self.hass)

    @callback
    def async_scan(self, *_: Any) -> None:
        """Scan for new entries."""
        # Do nothing.


@pytest.fixture
def mock_ssdp_scanner():
    """Mock ssdp Scanner."""
    with patch(
        "homeassistant.components.ssdp.Scanner", new=MockSsdpScanner
    ) as mock_ssdp_scanner:
        yield mock_ssdp_scanner
