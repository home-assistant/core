"""Support for MadVR remote control."""

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from madvr.errors import RetryExceededError
from madvr.madvr import Madvr

from homeassistant.components.remote import RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MadVRCoordinator
from .utils import cancel_tasks

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MadVR remote."""
    coordinator: MadVRCoordinator = entry.runtime_data

    madvr_client = coordinator.client

    async_add_entities(
        [
            MadvrRemote(hass, coordinator, madvr_client, entry.entry_id),
        ]
    )


class MadvrRemote(CoordinatorEntity, RemoteEntity):
    """Remote entity for the MadVR integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: MadVRCoordinator,
        madvr_client: Madvr,
        entry_id: str,
    ) -> None:
        """Initialize the remote entity."""
        super().__init__(coordinator)
        self.madvr_client = madvr_client
        self._attr_name = coordinator.name
        self._attr_unique_id = f"{entry_id}_remote"
        self.entry_id = hass.data[DOMAIN]["entry_id"]
        self._attr_should_poll = False
        self.tasks: list = []
        self.connection_event = self.madvr_client.connection_event
        self.command_queue: asyncio.Queue = asyncio.Queue()
        self.stop_processing_commands = asyncio.Event()
        self.madvr_client.set_update_callback(coordinator.handle_push_data)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        # open connection if not already connected
        await super().async_added_to_hass()

        # handle queue
        task_queue = self.hass.loop.create_task(self.handle_queue())
        self.tasks.append(task_queue)

        task_notif = self.hass.loop.create_task(self.madvr_client.read_notifications())
        self.tasks.append(task_notif)

        task_hb = self.hass.loop.create_task(self.madvr_client.send_heartbeat())
        self.tasks.append(task_hb)

    async def async_will_remove_from_hass(self) -> None:
        """Run when removed."""
        _LOGGER.debug("Removing from hass")
        self.madvr_client.stop()
        await self.madvr_client.close_connection()
        await cancel_tasks(self.madvr_client)
        for task in self.tasks:
            if not task.done():
                task.cancel()

    @property
    def is_on(self) -> bool:
        """Return true if the device is on."""
        return self.madvr_client.is_on

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        # Useful for making sensors
        return self.madvr_client.msg_dict

    async def handle_queue(self):
        """Handle command queue."""
        while True:
            await self.connection_event.wait()
            while (
                not self.command_queue.empty()
                and not self.stop_processing_commands.is_set()
            ):
                command = await self.command_queue.get()
                _LOGGER.debug("sending queue command %s", command)
                try:
                    await self.madvr_client.send_command(command)
                except ConnectionResetError:
                    _LOGGER.warning("Envy was turned off manually")
                    # update state
                    self._attr_is_on = False
                    self.async_write_ha_state()
                    await self.clear_state()
                except AttributeError:
                    _LOGGER.warning("Issue sending command from queue")
                except RetryExceededError:
                    _LOGGER.warning("Retry exceeded for command %s", command)
                except OSError as err:
                    _LOGGER.error("Unexpected error when sending command: %s", err)
                finally:
                    self.command_queue.task_done()

            if self.stop_processing_commands.is_set():
                self.clear_queue()
                _LOGGER.debug("Stopped processing commands")
                break

            await asyncio.sleep(0.1)

    def clear_queue(self):
        """Clear queue."""
        self.command_queue = asyncio.Queue()

    async def clear_state(self) -> None:
        """Clear state."""
        self.stop_processing_commands.set()
        self.clear_queue()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        _LOGGER.debug("Turning off")
        await self.clear_state()
        await self.madvr_client.power_off()
        self._attr_is_on = False
        self.async_write_ha_state()
        _LOGGER.debug("self._state is now: %s", self._attr_is_on)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the device."""
        _LOGGER.debug("Turning on device")
        # power state will be captured once the connection is established
        await self.madvr_client.power_on()
        self.stop_processing_commands.clear()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a command to one device."""
        _LOGGER.debug("adding command %s", command)
        await self.command_queue.put(command)
