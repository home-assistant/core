"""Tests for the Blue Current integration."""
from __future__ import annotations

from collections.abc import Callable
from unittest.mock import patch

from homeassistant.components.blue_current import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


class MockClient:
    """A mocked version of the blue current api Client class."""

    receiver: Callable

    def __init__(self, charge_point, charge_point_status, grid) -> None:
        """Initialize the mock client and sets the default responses."""
        self.charge_point = charge_point
        self.charge_point_status = charge_point_status
        self.grid = grid

    async def start_loop(self, receiver):
        """Set the receiver."""
        self.receiver = receiver

    async def get_charge_points(self):
        """Send a list of charge points to the callback."""
        await self.receiver(
            {
                "object": "CHARGE_POINTS",
                "data": [self.charge_point],
            }
        )

    async def get_status(self, evse_id: str):
        "Send the status of a charge point to the callback."
        await self.receiver(
            {
                "object": "CH_STATUS",
                "data": {"evse_id": evse_id} | self.charge_point_status,
            }
        )

    async def get_grid_status(self, evse_id: str):
        """Send the grid status to the callback."""
        await self.receiver({"object": "GRID_STATUS", "data": self.grid})

    async def wait_for_response(self):
        """Fake wait for response."""

    async def connect(self, token: str):
        """Fake connect."""

    async def disconnect(self):
        """Fake disconnect."""


async def init_integration(
    hass: HomeAssistant,
    platform,
    charge_point: dict,
    charge_point_status: dict,
    grid=None,
) -> MockClient:
    """Set up the Blue Current integration in Home Assistant."""

    client = MockClient(charge_point, charge_point_status, grid)

    with patch("homeassistant.components.blue_current.PLATFORMS", [platform]), patch(
        "homeassistant.components.blue_current.Client", return_value=client
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            entry_id="uuid",
            unique_id="uuid",
            data={"api_token": "123", "card": {"123"}},
        )
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    return client
