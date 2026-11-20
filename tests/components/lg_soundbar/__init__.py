"""Tests for the lg_soundbar component."""

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock

from aiotemescal import TemescalTimeoutError
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def set_answers(client: AsyncMock, answers: dict[str, dict[str, Any]]) -> None:
    """Answer requests with the given data per message; others time out."""

    async def request(
        msg: str, data: dict[str, Any] | None = None, cmd: str = "get"
    ) -> dict[str, Any]:
        if msg not in answers:
            raise TemescalTimeoutError(msg)
        return {"msg": msg, "data": answers[msg]}

    client.request.side_effect = request


def find_update_callback(client: AsyncMock) -> Callable[[dict[str, Any]], None]:
    """Return the callback the entity registered for device messages."""
    return client.subscribe.call_args.args[0]


def find_connection_callback(client: AsyncMock) -> Callable[[bool], None]:
    """Return the callback the entity registered for connection changes."""
    return client.subscribe_connection.call_args.args[0]
