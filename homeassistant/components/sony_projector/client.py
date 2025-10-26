"""Async helpers for the Sony Projector integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import partial
from typing import Any

import pysdcp


class ProjectorClientError(Exception):
    """Raised when projector communication fails."""


@dataclass(slots=True)
class ProjectorState:
    """Represents the power state of the projector."""

    is_on: bool


class ProjectorClient:
    """Wrapper around the synchronous pysdcp client with async helpers."""

    def __init__(self, host: str) -> None:
        """Initialize the client for a given host."""

        self._host = host
        self._projector = pysdcp.Projector(host)
        self._model: str | None = None
        self._serial: str | None = None

    @property
    def host(self) -> str:
        """Return the host the client talks to."""

        return self._host

    @property
    def model(self) -> str | None:
        """Return the cached model information, if any."""

        return self._model

    @property
    def serial(self) -> str | None:
        """Return the cached serial number, if any."""

        return self._serial

    async def async_get_state(self) -> ProjectorState:
        """Fetch and return the current projector state."""

        try:
            is_on = await self._async_call(self._projector.get_power)
        except (ConnectionError, OSError) as err:
            raise ProjectorClientError("Unable to query projector power state") from err

        return ProjectorState(is_on=bool(is_on))

    async def async_set_power(self, powered: bool) -> None:
        """Set the power state of the projector."""

        try:
            success = await self._async_call(self._projector.set_power, powered)
        except (ConnectionError, OSError) as err:
            raise ProjectorClientError("Unable to send power command") from err

        if not success:
            raise ProjectorClientError("Projector rejected the power command")

    async def async_validate_connection(self) -> None:
        """Validate connectivity by issuing a lightweight request."""

        await self.async_get_state()

    async def _async_call(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a synchronous pysdcp call in the executor."""

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))
