"""Cover Platform for Dio Chacon REV-SHUTTER devices."""
import logging
from typing import Any

from dio_chacon_wifi_api.const import DeviceTypeEnum, ShutterMoveEnum

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    EVENT_DIO_CHACON_DEVICE_STATE_CHANGED,
    EVENT_DIO_CHACON_DEVICE_STATE_RELOAD,
    MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Discover and configure covers."""

    data = hass.data[DOMAIN][config_entry.entry_id]
    dio_chacon_client = data

    list_devices = await dio_chacon_client.search_all_devices(
        device_type_to_search=DeviceTypeEnum.SHUTTER, with_state=True
    )

    if not list_devices:
        _LOGGER.info(
            "DIO Chacon did not setup covers because there are no devices of this type on this account %s",
            config_entry.title,
        )
        return

    device_list = []

    _LOGGER.debug("List of devices %s", list_devices)

    for device in list_devices.values():
        device_list.append(
            DioChaconShade(
                dio_chacon_client,
                device["id"],
                device["name"],
                device["openlevel"],
                device["movement"],
                device["connected"],
                device["model"],
            )
        )

        _LOGGER.info(
            "Adding DIO Chacon SHUTTER Cover with id %s, name %s, openlevel %s, movement %s and connected %s",
            device["id"],
            device["name"],
            device["openlevel"],
            device["movement"],
            device["connected"],
        )

    async_add_entities(device_list)


class DioChaconShade(RestoreEntity, CoverEntity):
    """Object for controlling a Dio Chacon cover."""

    _attr_should_poll = False
    _attr_assumed_state = True
    _attr_has_entity_name = False

    def __init__(
        self,
        dio_chacon_client,
        target_id,
        name,
        openlevel,
        movement,
        connected,
        model,
        device_class=CoverDeviceClass.SHUTTER,
    ) -> None:
        """Initialize the cover."""
        self.dio_chacon_client = dio_chacon_client
        self._target_id = target_id
        self._attr_unique_id = target_id
        self._attr_name = name
        self._attr_current_cover_position = openlevel
        self._attr_is_closed = openlevel == 0
        self._attr_is_closing = movement == ShutterMoveEnum.DOWN.value
        self._attr_is_opening = movement == ShutterMoveEnum.UP.value
        self._attr_available = connected
        self._attr_device_class = device_class
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._target_id)},
            manufacturer=MANUFACTURER,
            name=name,
            model=model,
        )
        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""

        _LOGGER.debug("Close cover %s , %s", self._target_id, self._attr_name)

        self._attr_is_closing = True
        self.async_write_ha_state()

        await self.dio_chacon_client.move_shutter_direction(
            self._target_id, ShutterMoveEnum.DOWN
        )

        # Closed signal is managed via a callback _on_device_state_changed

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""

        _LOGGER.debug("Open cover %s , %s", self._target_id, self._attr_name)

        self._attr_is_opening = True
        self.async_write_ha_state()

        await self.dio_chacon_client.move_shutter_direction(
            self._target_id, ShutterMoveEnum.UP
        )

        # Opened signal is managed via a callback _on_device_state_changed

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""

        _LOGGER.debug("Stop cover %s , %s", self._target_id, self._attr_name)

        await self.dio_chacon_client.move_shutter_direction(
            self._target_id, ShutterMoveEnum.STOP
        )

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover open position in percentage."""
        position: int = kwargs[ATTR_POSITION]

        _LOGGER.debug(
            "Set cover position %i, %s , %s", position, self._target_id, self._attr_name
        )

        await self.dio_chacon_client.move_shutter_percentage(self._target_id, position)

        # Movement signal is managed via a callback _on_device_state_changed

    async def async_added_to_hass(self) -> None:
        """Complete the initialization."""
        await super().async_added_to_hass()

        # Add Listener for changes from the callback defined in __init__.py
        listener_callback_event = self.hass.bus.async_listen(
            EVENT_DIO_CHACON_DEVICE_STATE_CHANGED, self._on_device_state_changed
        )
        # Remove listener on entity destruction
        self.async_on_remove(listener_callback_event)

        # Add Listener for reload service
        listener_callback_event = self.hass.bus.async_listen(
            EVENT_DIO_CHACON_DEVICE_STATE_RELOAD, self._on_device_state_reload
        )
        # Remove listener on entity destruction
        self.async_on_remove(listener_callback_event)

    def _on_device_state_changed(self, event):
        # On server side event of state change
        if event.data.get("id") == self._target_id:
            _LOGGER.debug("Event state changed received : %s", event)
            self._effectively_update_entity_state(event.data)

    def _on_device_state_reload(self, event):
        # Simply launches a forced update calling async_update
        self.async_schedule_update_ha_state(force_refresh=True)

    def _effectively_update_entity_state(self, data: dict[str, Any]) -> None:
        self._attr_available = data["connected"]
        openlevel = data["openlevel"]
        self._attr_current_cover_position = openlevel
        self._attr_is_closed = openlevel == 0
        movement = data["movement"]
        if movement == ShutterMoveEnum.DOWN.value:
            self._attr_is_closing = True
        elif movement == ShutterMoveEnum.UP.value:
            self._attr_is_opening = True
        elif movement == ShutterMoveEnum.STOP.value:
            self._attr_is_closing = False
            self._attr_is_opening = False
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Get the latest data from the Dio Chacon API and update the states."""
        _LOGGER.debug(
            "Launching reload of cover device state for id %s, and name %s",
            self._target_id,
            self._attr_name,
        )
        data = await self.dio_chacon_client.get_status_details([self._target_id])
        details = data[self._target_id]
        self._effectively_update_entity_state(details)
