"""Support for SimpliSafe alarm systems."""

from __future__ import annotations

from collections.abc import Iterable

from simplipy.device import Device, DeviceTypes
from simplipy.system.v3 import SystemV3
from simplipy.websocket import (
    EVENT_CONNECTION_LOST,
    EVENT_CONNECTION_RESTORED,
    EVENT_LOCK_LOCKED,
    EVENT_LOCK_UNLOCKED,
    EVENT_POWER_OUTAGE,
    EVENT_POWER_RESTORED,
    WebsocketEvent,
)

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import SimpliSafe
from .const import (
    ATTR_LAST_EVENT_INFO,
    ATTR_LAST_EVENT_SENSOR_NAME,
    ATTR_LAST_EVENT_SENSOR_TYPE,
    ATTR_LAST_EVENT_TIMESTAMP,
    ATTR_SYSTEM_ID,
    DISPATCHER_TOPIC_WEBSOCKET_EVENT,
    DOMAIN,
    LOGGER,
)
from .typing import SystemType

DEFAULT_CONFIG_URL = "https://webapp.simplisafe.com/new/#/dashboard"
DEFAULT_ENTITY_MODEL = "Alarm control panel"
DEFAULT_ERROR_THRESHOLD = 2

WEBSOCKET_EVENTS_REQUIRING_SERIAL = [EVENT_LOCK_LOCKED, EVENT_LOCK_UNLOCKED]


class SimpliSafeEntity(CoordinatorEntity[DataUpdateCoordinator[None]]):
    """Define a base SimpliSafe entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        simplisafe: SimpliSafe,
        system: SystemType,
        *,
        device: Device | None = None,
        additional_websocket_events: Iterable[str] | None = None,
    ) -> None:
        """Initialize."""
        assert simplisafe.coordinator
        super().__init__(simplisafe.coordinator)

        # SimpliSafe can incorrectly return an error state when there isn't any
        # error. This can lead to entities having an unknown state frequently.
        # To protect against that, we measure an error count for each entity and only
        # mark the state as unavailable if we detect a few in a row:
        self._error_count = 0

        if device:
            model = device.type.name.capitalize().replace("_", " ")
            device_name = f"{device.name.capitalize()} {model}"
            serial = device.serial
        else:
            model = device_name = DEFAULT_ENTITY_MODEL
            serial = system.serial

        event = simplisafe.initial_event_to_use[system.system_id]

        if raw_type := event.get("sensorType"):
            try:
                device_type = DeviceTypes(raw_type)
            except ValueError:
                device_type = DeviceTypes.UNKNOWN
        else:
            device_type = DeviceTypes.UNKNOWN

        self._attr_extra_state_attributes = {
            ATTR_LAST_EVENT_INFO: event.get("info"),
            ATTR_LAST_EVENT_SENSOR_NAME: event.get("sensorName"),
            ATTR_LAST_EVENT_SENSOR_TYPE: device_type.name.lower(),
            ATTR_LAST_EVENT_TIMESTAMP: event.get("eventTimestamp"),
            ATTR_SYSTEM_ID: system.system_id,
        }

        self._attr_device_info = DeviceInfo(
            configuration_url=DEFAULT_CONFIG_URL,
            identifiers={(DOMAIN, serial)},
            manufacturer="SimpliSafe",
            model=model,
            name=device_name,
            via_device=(DOMAIN, str(system.system_id)),
        )

        self._attr_unique_id = serial
        self._device = device
        self._online = True
        self._simplisafe = simplisafe
        self._system = system
        self._websocket_events_to_listen_for = [
            EVENT_CONNECTION_LOST,
            EVENT_CONNECTION_RESTORED,
            EVENT_POWER_OUTAGE,
            EVENT_POWER_RESTORED,
        ]
        if additional_websocket_events:
            self._websocket_events_to_listen_for += additional_websocket_events

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        # We can easily detect if the V3 system is offline, but no simple check exists
        # for the V2 system. Therefore, assuming the coordinator hasn't failed, we mark
        # the entity as available if:
        #   1. We can verify that the system is online (assuming True if we can't)
        #   2. We can verify that the entity is online
        if isinstance(self._system, SystemV3):
            system_offline = self._system.offline
        else:
            system_offline = False

        return (
            self._error_count < DEFAULT_ERROR_THRESHOLD
            and self._online
            and not system_offline
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the entity with new REST API data."""
        if self.coordinator.last_update_success:
            self.async_reset_error_count()
        else:
            self.async_increment_error_count()

        self.async_update_from_rest_api()
        self.async_write_ha_state()

    @callback
    def _handle_websocket_update(self, event: WebsocketEvent) -> None:
        """Update the entity with new websocket data."""
        # Ignore this event if it belongs to a system other than this one:
        if event.system_id != self._system.system_id:
            return

        # Ignore this event if this entity hasn't expressed interest in its type:
        if event.event_type not in self._websocket_events_to_listen_for:
            return

        # Ignore this event if it belongs to a entity with a different serial
        # number from this one's:
        if (
            self._device
            and event.event_type in WEBSOCKET_EVENTS_REQUIRING_SERIAL
            and event.sensor_serial != self._device.serial
        ):
            return

        sensor_type: str | None
        if event.sensor_type:
            sensor_type = event.sensor_type.name
        else:
            sensor_type = None

        self._attr_extra_state_attributes.update(
            {
                ATTR_LAST_EVENT_INFO: event.info,
                ATTR_LAST_EVENT_SENSOR_NAME: event.sensor_name,
                ATTR_LAST_EVENT_SENSOR_TYPE: sensor_type,
                ATTR_LAST_EVENT_TIMESTAMP: event.timestamp,
            }
        )

        # It's unknown whether these events reach the base station (since the connection
        # is lost); we include this for completeness and coverage:
        if event.event_type in (EVENT_CONNECTION_LOST, EVENT_POWER_OUTAGE):
            self._online = False
            return

        # If the base station comes back online, set entities to available, but don't
        # instruct the entities to update their state (since there won't be anything new
        # until the next websocket event or REST API update:
        if event.event_type in (EVENT_CONNECTION_RESTORED, EVENT_POWER_RESTORED):
            self._online = True
            return

        self.async_update_from_websocket_event(event)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                DISPATCHER_TOPIC_WEBSOCKET_EVENT.format(self._system.system_id),
                self._handle_websocket_update,
            )
        )

        self.async_update_from_rest_api()

    @callback
    def async_increment_error_count(self) -> None:
        """Increment this entity's error count."""
        LOGGER.debug('Error for entity "%s" (total: %s)', self.name, self._error_count)
        self._error_count += 1

    @callback
    def async_reset_error_count(self) -> None:
        """Reset this entity's error count."""
        if self._error_count == 0:
            return

        LOGGER.debug('Resetting error count for "%s"', self.name)
        self._error_count = 0

    @callback
    def async_update_from_rest_api(self) -> None:
        """Update the entity when new data comes from the REST API."""

    @callback
    def async_update_from_websocket_event(self, event: WebsocketEvent) -> None:
        """Update the entity when new data comes from the websocket."""
