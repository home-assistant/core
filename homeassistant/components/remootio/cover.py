"""Support for by a Remootio device controlled garage door or gate."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from aioremootio import Event, EventType, Listener, RemootioClient, State, StateChange

from homeassistant.components import cover
from homeassistant.components.cover import CoverDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_CLASS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_SERIAL_NUMBER, DOMAIN, EVENT_HANDLER_CALLBACK, REMOOTIO_CLIENT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an ``RemootioCover`` entity based on the given configuration entry."""

    _LOGGER.debug(
        "Doing async_setup_entry. config_entry [%s] hass.data[%s][%s] [%s]",
        config_entry.as_dict(),
        DOMAIN,
        config_entry.entry_id,
        hass.data[DOMAIN][config_entry.entry_id],
    )

    serial_number: str = config_entry.data[CONF_SERIAL_NUMBER]
    device_class: CoverDeviceClass = config_entry.data[CONF_DEVICE_CLASS]
    remootio_client: RemootioClient = hass.data[DOMAIN][config_entry.entry_id][
        REMOOTIO_CLIENT
    ]
    event_handler_callback: Callable[[RemootioCoverEvent], None] = hass.data[DOMAIN][
        config_entry.entry_id
    ][EVENT_HANDLER_CALLBACK]

    async_add_entities(
        [
            RemootioCover(
                serial_number,
                config_entry.title,
                device_class,
                remootio_client,
                event_handler_callback,
            )
        ]
    )


class RemootioCover(cover.CoverEntity):
    """Cover entity which represents an Remootio device controlled garage door or gate."""

    _remootio_client: RemootioClient
    _event_handler_callback: Callable[[RemootioCoverEvent], None]
    _attr_has_entity_name: bool = True
    _attr_should_poll: bool = False
    _attr_supported_features: int = cover.SUPPORT_OPEN | cover.SUPPORT_CLOSE

    def __init__(
        self,
        unique_id: str,
        name: str,
        device_class: CoverDeviceClass,
        remootio_client: RemootioClient,
        event_handler_callback: Callable[[RemootioCoverEvent], None],
    ) -> None:
        """Initialize this cover entity."""
        super().__init__()
        self._attr_unique_id = unique_id
        self._attr_device_class = device_class
        self._remootio_client = remootio_client
        self._event_handler_callback = event_handler_callback
        self._attr_device_info = DeviceInfo(
            name=name,
            manufacturer="Assemblabs Ltd",
        )

    async def async_added_to_hass(self) -> None:
        """Register listeners to the used Remootio client to be notified on state changes and events."""

        _LOGGER.debug(
            "Doing async_added_to_hass for %s with entity id %s",
            self.__class__,
            self.entity_id,
        )

        await self._remootio_client.add_state_change_listener(
            RemootioCoverStateChangeListener(self)
        )

        await self._remootio_client.add_event_listener(
            RemootioCoverEventListener(self, self._event_handler_callback)
        )

        self.async_schedule_update_ha_state(force_refresh=True)

    async def async_will_remove_from_hass(self) -> None:
        """Remove listeners from the used Remootio client."""

        _LOGGER.debug(
            "Doing async_will_remove_from_hass for %s with entity id %s",
            self.__class__,
            self.entity_id,
        )

        removed_listerners_count: int = 0

        removed_listerners_count = (
            await self._remootio_client.remove_state_change_listeners()
        )
        _LOGGER.debug(
            "%d state change listeners was succefully removed from Remootio client",
            removed_listerners_count,
        )

        removed_listerners_count = await self._remootio_client.remove_event_listeners()
        _LOGGER.debug(
            "%d event listeners was succefully removed from Remootio client",
            removed_listerners_count,
        )

    async def async_update(self) -> None:
        """Trigger state update of the used Remootio client."""
        await self._remootio_client.trigger_state_update()

    @property
    def is_opening(self) -> bool | None:
        """Return True when the Remootio controlled garage door or gate is currently opening."""
        return self._remootio_client.state == State.OPENING

    @property
    def is_closing(self) -> bool | None:
        """Return True when the Remootio controlled garage door or gate is currently closing."""
        return self._remootio_client.state == State.CLOSING

    @property
    def is_closed(self) -> bool | None:
        """Return True when the Remootio controlled garage door or gate is currently closed."""
        return self._remootio_client.state == State.CLOSED

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the Remootio controlled garage door or gate."""
        await self._remootio_client.trigger_open()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the Remootio controlled garage door or gate."""
        await self._remootio_client.trigger_close()


class RemootioCoverStateChangeListener(Listener[StateChange]):
    """Listener to be invoked when Remootio controlled garage door or gate changes its state."""

    _owner: RemootioCover

    def __init__(self, owner: RemootioCover) -> None:
        """Initialize an instance of this class."""
        super().__init__()
        self._owner = owner

    async def execute(self, client: RemootioClient, subject: StateChange) -> None:
        """Execute this listener. Tell Home Assistant that the Remootio controlled garage door or gate has changed its state."""
        _LOGGER.debug(
            "Telling Home Assistant that the Remootio controlled garage door or gate has changed its state. RemootioClientState [%s] RemootioCoverEntityId [%s] RemootioCoverUniqueId [%s] RemootioCoverState [%s]",
            client.state,
            self._owner.entity_id,
            self._owner.unique_id,
            self._owner.state,
        )
        self._owner.async_write_ha_state()


class RemootioCoverEvent:
    """Represents an event to be handled."""

    _type: str
    _entity_id: str
    _entity_name: str | None
    _device_serial_number: str | None

    def __init__(
        self,
        client_event_type: EventType,
        entity_id: str,
        entity_name: str | None,
        device_serial_number: str | None,
    ) -> None:
        """Initialize an instance of this class."""
        self._type = f"{DOMAIN.lower()}_{client_event_type.name.lower()}"
        self._entity_id = entity_id
        self._entity_name = entity_name
        self._device_serial_number = device_serial_number

    @property
    def type(self) -> str:
        """Event's type."""
        return self._type

    @property
    def entity_id(self) -> str:
        """Id of the entity which has triggered the event."""
        return self._entity_id

    @property
    def entity_name(self) -> str | None:
        """Name of the entity which has triggered the event."""
        return self._entity_name

    @property
    def device_serial_number(self) -> str | None:
        """Remootio device's serial number which has triggered the event."""
        return self._device_serial_number


class RemootioCoverEventListener(Listener[Event]):
    """Listener to be invoked on an event sent by the Remmotio device."""

    _owner: RemootioCover
    _event_handler_callback: Callable[[RemootioCoverEvent], None]

    def __init__(
        self,
        owner: RemootioCover,
        event_handler_callback: Callable[[RemootioCoverEvent], None],
    ) -> None:
        """Initialize an instance of this class."""
        super().__init__()
        self._owner = owner
        self._event_handler_callback = event_handler_callback

    async def execute(self, client: RemootioClient, subject: Event) -> None:
        """Execute this listener. Fire events in Home Assistant based on events sent by the Remootio device.

        Fires the event remootio_left_open in Home Assistant when the Remootio controlled garage door or gate has been left open.
        As event data the serial number of the Remootio device (also the id of the entity which represents it in Home Assistant) and
        the name of the entity which represents the Remootio device in Home Assistant will be passed to the fired event.
        """
        if subject.type == EventType.LEFT_OPEN:
            event: RemootioCoverEvent = RemootioCoverEvent(
                subject.type,
                self._owner.entity_id,
                self._owner.name,
                self._owner.unique_id,
            )

            self._event_handler_callback(event)
