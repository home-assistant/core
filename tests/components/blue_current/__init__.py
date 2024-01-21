"""Tests for the Blue Current integration."""
from __future__ import annotations

from asyncio import Event, sleep
from functools import partial
from unittest.mock import MagicMock, patch

from bluecurrent_api import Client

from homeassistant.components.blue_current import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DEFAULT_CHARGE_POINT = {
    "evse_id": "101",
    "model_type": "",
    "name": "",
}


async def connect(client, token: str):
    """Set the connected event."""
    if client.connect_exception:
        # Raise exception once.
        temp = client.connect_exception
        client.connect_exception = None
        raise temp

    client.connected.set()
    client.connected.clear()


async def start_loop(client, receiver):
    """Set the receiver."""
    client.receiver = receiver
    client.loop_start_task.set()

    while True:
        if client.loop_exception:
            # Raise exception once.
            temp = client.loop_exception
            client.loop_exception = None
            raise temp
        await sleep(0)


async def get_charge_points(client, charge_point: dict) -> None:
    """Send a list of charge points to the callback."""
    await client.loop_start_task.wait()
    await client.receiver(
        {
            "object": "CHARGE_POINTS",
            "data": [charge_point],
        }
    )


async def get_status(client, status: dict, evse_id: str) -> None:
    """Send the status of a charge point to the callback."""
    await client.receiver(
        {
            "object": "CH_STATUS",
            "data": {"evse_id": evse_id} | status,
        }
    )


async def get_grid_status(client, grid: dict, evse_id: str) -> None:
    """Send the grid status to the callback."""
    await client.receiver({"object": "GRID_STATUS", "data": grid})


def create_client_mock(
    charge_point: dict,
    status: dict | None = None,
    grid: dict | None = None,
) -> MagicMock:
    """Create a mock of the bluecurrent-api Client."""
    client_mock = MagicMock(spec=Client)

    client_mock.receiver = None

    client_mock.loop_exception = None
    client_mock.connect_exception = None

    client_mock.connected = Event()
    client_mock.loop_start_task = Event()

    client_mock.connect.side_effect = partial(connect, client_mock)
    client_mock.start_loop.side_effect = partial(start_loop, client_mock)
    client_mock.get_charge_points.side_effect = partial(
        get_charge_points, client_mock, charge_point
    )
    client_mock.get_status.side_effect = partial(get_status, client_mock, status)
    client_mock.get_grid_status.side_effect = partial(
        get_grid_status, client_mock, grid
    )

    return client_mock


async def init_integration(
    hass: HomeAssistant,
    platform="",
    charge_point: dict | None = None,
    status: dict | None = None,
    grid: dict | None = None,
) -> MagicMock:
    """Set up the Blue Current integration in Home Assistant."""

    if charge_point is None:
        charge_point = DEFAULT_CHARGE_POINT

    client_mock = create_client_mock(charge_point, status, grid)

    with patch("homeassistant.components.blue_current.PLATFORMS", [platform]), patch(
        "homeassistant.components.blue_current.Client", return_value=client_mock
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
    return client_mock
