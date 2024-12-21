"""Define a base coordinator for Bluesound entities."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
import contextlib
from dataclasses import dataclass, replace
from datetime import timedelta
import logging

from pyblu import Input, Player, Preset, Status, SyncStatus
from pyblu.errors import PlayerUnreachableError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

NODE_OFFLINE_CHECK_TIMEOUT = timedelta(minutes=3)
PRESET_AND_INPUTS_INTERVAL = timedelta(minutes=15)


@dataclass
class BluesoundData:
    """Define a class to hold Bluesound data."""

    sync_status: SyncStatus
    status: Status
    presets: list[Preset]
    inputs: list[Input]

    is_online: bool


def cancel_task(task: asyncio.Task) -> Callable[[], Coroutine[None, None, None]]:
    """Cancel a task."""

    async def _cancel_task() -> None:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    return _cancel_task


class BluesoundCoordinator(DataUpdateCoordinator[BluesoundData]):
    """Define an object to hold Bluesound data."""

    def __init__(
        self, hass: HomeAssistant, player: Player, sync_status: SyncStatus
    ) -> None:
        """Initialize."""
        self.player = player
        self._inital_sync_status = sync_status

        super().__init__(
            hass,
            logger=_LOGGER,
            name=sync_status.name,
        )

    async def _async_setup(self) -> None:
        assert self.config_entry is not None

        preset = await self.player.presets()
        inputs = await self.player.inputs()
        status = await self.player.status()

        self.async_set_updated_data(
            BluesoundData(
                sync_status=self._inital_sync_status,
                status=status,
                presets=preset,
                inputs=inputs,
                is_online=True,
            )
        )

        status_loop_task = self.hass.async_create_background_task(
            self._poll_status_loop(),
            name=f"bluesound.poll_status_loop_{self.data.sync_status.id}",
        )
        self.config_entry.async_on_unload(cancel_task(status_loop_task))

        sync_status_loop_task = self.hass.async_create_background_task(
            self._poll_sync_status_loop(),
            name=f"bluesound.poll_sync_status_loop_{self.data.sync_status.id}",
        )
        self.config_entry.async_on_unload(cancel_task(sync_status_loop_task))

        presets_and_inputs_loop_task = self.hass.async_create_background_task(
            self._poll_presets_and_inputs_loop(),
            name=f"bluesound.poll_presets_and_inputs_loop_{self.data.sync_status.id}",
        )
        self.config_entry.async_on_unload(cancel_task(presets_and_inputs_loop_task))

    async def _async_update_data(self) -> BluesoundData:
        return self.data

    def _set_offline(self) -> None:
        _LOGGER.error(
            "Node %s is offline or threw an unexpected error, retrying later",
            self.data.sync_status.id,
        )
        self.async_set_updated_data(
            replace(
                self.data,
                is_online=False,
            )
        )

    async def _poll_presets_and_inputs_loop(self) -> None:
        while True:
            await asyncio.sleep(PRESET_AND_INPUTS_INTERVAL.total_seconds())
            try:
                preset = await self.player.presets()
                inputs = await self.player.inputs()
                self.async_set_updated_data(
                    replace(
                        self.data,
                        presets=preset,
                        inputs=inputs,
                        is_online=True,
                    )
                )
            except PlayerUnreachableError:
                self._set_offline()
            except asyncio.CancelledError:
                return
            except:  # noqa: E722 - this loop should never stop
                self._set_offline()

    async def _poll_status_loop(self) -> None:
        """Loop which polls the status of the player."""
        while True:
            try:
                status = await self.player.status(
                    etag=self.data.status.etag, poll_timeout=120, timeout=125
                )
                self.async_set_updated_data(
                    replace(
                        self.data,
                        status=status,
                        is_online=True,
                    )
                )
            except PlayerUnreachableError:
                self._set_offline()
                await asyncio.sleep(NODE_OFFLINE_CHECK_TIMEOUT.total_seconds())
            except asyncio.CancelledError:
                return
            except:  # noqa: E722 - this loop should never stop
                self._set_offline()
                await asyncio.sleep(NODE_OFFLINE_CHECK_TIMEOUT.total_seconds())

    async def _poll_sync_status_loop(self) -> None:
        """Loop which polls the sync status of the player."""
        while True:
            try:
                sync_status = await self.player.sync_status(
                    etag=self.data.sync_status.etag, poll_timeout=120, timeout=125
                )
                self.async_set_updated_data(
                    replace(
                        self.data,
                        sync_status=sync_status,
                        is_online=True,
                    )
                )
            except PlayerUnreachableError:
                self._set_offline()
                await asyncio.sleep(NODE_OFFLINE_CHECK_TIMEOUT.total_seconds())
            except asyncio.CancelledError:
                raise
            except:  # noqa: E722 - all errors must be caught for this loop
                self._set_offline()
                await asyncio.sleep(NODE_OFFLINE_CHECK_TIMEOUT.total_seconds())
