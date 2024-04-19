"""Tests for the Blue Current integration."""

from __future__ import annotations

from asyncio import Event, Future
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from bluecurrent_api import Client

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DEFAULT_CHARGE_POINT = {
    "evse_id": "101",
    "model_type": "",
    "name": "",
}


@dataclass
class FutureContainer:
    """Dataclass that stores a future."""

    future: Future


def create_client_mock(
    hass: HomeAssistant,
    future_container: FutureContainer,
    started_loop: Event,
    charge_point: dict,
    status: dict,
    grid: dict,
) -> MagicMock:
    """Create a mock of the bluecurrent-api Client."""
    client_mock = MagicMock(spec=Client)
    received_charge_points = Event()

    async def wait_for_charge_points():
        """Wait until chargepoints are received."""
        await received_charge_points.wait()

    async def connect(receiver, on_open):
        """Set the receiver and await future."""
        client_mock.receiver = receiver
        await on_open()

        started_loop.set()
        started_loop.clear()

        if future_container.future.done():
            future_container.future = hass.loop.create_future()
        await future_container.future

    async def get_charge_points() -> None:
        """Send a list of charge points to the callback."""
        await client_mock.receiver(
            {
                "object": "CHARGE_POINTS",
                "data": [charge_point],
            }
        )
        received_charge_points.set()

    async def get_status(evse_id: str) -> None:
        """Send the status of a charge point to the callback."""
        await client_mock.receiver(
            {
                "object": "CH_STATUS",
                "data": {"evse_id": evse_id} | status,
            }
        )

    async def get_grid_status(evse_id: str) -> None:
        """Send the grid status to the callback."""
        await client_mock.receiver({"object": "GRID_STATUS", "data": grid})

    client_mock.connect.side_effect = connect
    client_mock.wait_for_charge_points.side_effect = wait_for_charge_points
    client_mock.get_charge_points.side_effect = get_charge_points
    client_mock.get_status.side_effect = get_status
    client_mock.get_grid_status.side_effect = get_grid_status

    return client_mock


async def init_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    platform="",
    charge_point: dict | None = None,
    status: dict | None = None,
    grid: dict | None = None,
) -> tuple[MagicMock, Event, FutureContainer]:
    """Set up the Blue Current integration in Home Assistant."""

    if charge_point is None:
        charge_point = DEFAULT_CHARGE_POINT

    if status is None:
        status = {}

    if grid is None:
        grid = {}

    future_container = FutureContainer(hass.loop.create_future())
    started_loop = Event()

    client_mock = create_client_mock(
        hass, future_container, started_loop, charge_point, status, grid
    )

    with (
        patch("homeassistant.components.blue_current.PLATFORMS", [platform]),
        patch("homeassistant.components.blue_current.Client", return_value=client_mock),
    ):
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    return client_mock, started_loop, future_container
