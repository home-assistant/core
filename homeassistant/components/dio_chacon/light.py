"""Light Platform for Dio Chacon REV-LIGHT devices."""
import logging
from typing import Any

from dio_chacon_wifi_api.const import DeviceTypeEnum

from homeassistant.components.light import ColorMode, LightEntity
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
    """Discover and configure lights."""

    data = hass.data[DOMAIN][config_entry.entry_id]
    dio_chacon_client = data

    list_devices = await dio_chacon_client.search_all_devices(
        device_type_to_search=DeviceTypeEnum.LIGHT, with_state=True
    )

    if not list_devices:
        _LOGGER.error("DIO Chacon failed to setup because of an error")
        return

    cover_list = []

    _LOGGER.debug("List of devices %s", list_devices)

    for device in list_devices.values():
        cover_list.append(
            DioChaconShade(
                dio_chacon_client,
                device["id"],
                device["name"],
                device["is_on"],
                device["connected"],
                device["model"],
            )
        )

        _LOGGER.debug(
            "Adding DIO Chacon LIGHT with id %s, name %s, is_on %s, and connected %s",
            device["id"],
            device["name"],
            device["is_on"],
            device["connected"],
        )

    async_add_entities(cover_list)


class DioChaconShade(RestoreEntity, LightEntity):
    """Object for controlling a Dio Chacon cover."""

    _attr_should_poll = False
    _attr_assumed_state = True
    _attr_has_entity_name = False
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF

    def __init__(
        self, dio_chacon_client, target_id, name, is_on, connected, model
    ) -> None:
        """Initialize the cover."""
        self.dio_chacon_client = dio_chacon_client
        self._target_id = target_id
        self._attr_unique_id = target_id
        self._attr_name = name
        self._attr_is_on = is_on
        self._attr_available = connected
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._target_id)},
            manufacturer=MANUFACTURER,
            name=name,
            model=model,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""

        _LOGGER.debug("Turn on the light %s , %s", self._target_id, self._attr_name)

        await self.dio_chacon_client.switch_light(self._target_id, True)

        # Effective state received via callback _on_device_state_changed

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""

        _LOGGER.debug("Turn off the light %s , %s", self._target_id, self._attr_name)

        await self.dio_chacon_client.switch_light(self._target_id, False)

        # Effective state received via callback _on_device_state_changed

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
        is_on = data["is_on"]
        self._attr_is_on = is_on
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Get the latest data from the Dio Chacon API and update the states."""
        _LOGGER.debug(
            "Launching reload of cover device state for id : %s", self._target_id
        )
        data = await self.dio_chacon_client.get_status_details([self._target_id])
        details = data[self._target_id]
        self._effectively_update_entity_state(details)
