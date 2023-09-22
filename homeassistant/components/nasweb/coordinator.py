"""Message routing coordinators for handling NASweb push notifications."""
import asyncio
import logging
from typing import Any, Optional

from aiohttp import web
from webio_api import Output as NASwebOutput, WebioAPI
from webio_api.const import KEY_DEVICE_SERIAL, KEY_OUTPUTS, KEY_TYPE, TYPE_STATUS_UPDATE

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .relay_switch import RelaySwitch

_LOGGER = logging.getLogger(__name__)


class NotificationCoordinator:
    """Coordinator redirecting push notifications for this integration to appropriate NASwebCoordinator."""

    def __init__(self) -> None:
        """Initialize coordinator."""
        self._coordinators: dict[str, NASwebCoordinator] = {}

    def add_coordinator(self, serial: str, cord: "NASwebCoordinator") -> None:
        """Remove NASwebCoordinator to possible notification targets."""
        self._coordinators[serial] = cord
        _LOGGER.debug("Added NASwebCoordinator for NASweb[%s]", serial)

    def remove_coordinator(self, serial: str) -> None:
        """Remove NASwebCoordinator from possible notification targets."""
        if self._coordinators.pop(serial, None) is None:
            _LOGGER.warning("Trying to remove nonexistent NASwebCoordinator")
        _LOGGER.debug("Removed NASwebCoordinator for NASweb[%s]", serial)

    def has_coordinators(self) -> bool:
        """Check if there is any registered coordinator for push notifications."""
        return len(self._coordinators) > 0

    async def check_connection(self, serial: str) -> bool:
        """Wait for first status update to confirm connection with NASweb."""
        nasweb_coordinator = self._coordinators.get(serial)
        if nasweb_coordinator is None:
            _LOGGER.error("Cannot check connection. No device match serial number")
            return False
        counter = 0
        _LOGGER.debug("Checking connection with: %s", serial)
        while not nasweb_coordinator.is_connection_confirmed() and counter < 10:
            await asyncio.sleep(1)
            counter += 1
            _LOGGER.debug("Checking connection with: %s (%s)", serial, counter)
        return nasweb_coordinator.is_connection_confirmed()

    async def handle_notification(self, request: web.BaseRequest) -> web.Response:
        """NASweb push notification handler."""
        if not self.has_coordinators():
            return web.Response()
        notification = await request.json()
        serial = notification.get(KEY_DEVICE_SERIAL, None)
        _LOGGER.debug("Received push: %s", notification)
        if serial is None:
            _LOGGER.warning("Received notification without nasweb identifier")
            return web.Response()
        nasweb_coordinator = self._coordinators.get(serial)
        if nasweb_coordinator is None:
            _LOGGER.warning("Received notification for not registered nasweb")
            return web.Response()
        nasweb_coordinator.handle_push_notification(notification)
        return web.Response()


class NASwebCoordinator(DataUpdateCoordinator):
    """Coordinator managing status of single NASweb device."""

    def __init__(
        self, hass: HomeAssistant, webio_api: WebioAPI, name: str = "NASweb[default]"
    ) -> None:
        """Initialize NASweb coordinator."""
        self._hass = hass
        self._connection_confirmed = False
        super().__init__(hass, _LOGGER, name=name)
        self.webio_api: WebioAPI = webio_api
        self.async_add_switch_callback: Optional[AddEntitiesCallback] = None
        data: dict[str, Any] = {}
        data[KEY_OUTPUTS] = self.webio_api.outputs
        self.async_set_updated_data(data)

    def is_connection_confirmed(self) -> bool:
        """Check whether coordinator received status update from NASweb."""
        return self._connection_confirmed

    def handle_push_notification(self, notification: dict) -> None:
        """Handle incoming push notification from NASweb."""
        msg_type = notification.get(KEY_TYPE)
        _LOGGER.debug("Received push notification: %s", msg_type)

        if msg_type == TYPE_STATUS_UPDATE:
            self.process_status_update(notification)
            self._connection_confirmed = True

    def process_status_update(self, new_status: dict) -> None:
        """Process status update from NASweb."""
        new_objects = self.webio_api.update_device_status(new_status)
        new_outputs = new_objects[KEY_OUTPUTS]
        if len(new_outputs) > 0:
            self._add_switch_entities(new_outputs)
        self.async_set_updated_data(self.data)

    def _add_switch_entities(self, switches: list[RelaySwitch]) -> None:
        if self.async_add_switch_callback is not None:
            new_switch_entities: list[RelaySwitch] = []
            for zone in switches:
                if not isinstance(zone, NASwebOutput):
                    _LOGGER.error("Cannot create RelaySwitch without NASwebOutput")
                    continue
                new_zone = RelaySwitch(self, zone)
                new_switch_entities.append(new_zone)
            self._hass.async_add_executor_job(
                self.async_add_switch_callback, new_switch_entities
            )
