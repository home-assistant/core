"""Switch Platform for Dio Chacon REV-LIGHT and switch plug devices."""

import logging
from typing import Any

from dio_chacon_wifi_api.const import DeviceTypeEnum

from homeassistant.components.switch import SwitchEntity
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
    """Discover and configure switches."""

    data = hass.data[DOMAIN][config_entry.entry_id]
    dio_chacon_client = data

    list_devices = await dio_chacon_client.search_all_devices(
        device_type_to_search=[DeviceTypeEnum.SWITCH_LIGHT, DeviceTypeEnum.SWITCH_PLUG],
        with_state=True,
    )

    if not list_devices:
        _LOGGER.info(
            "DIO Chacon did not setup switches because there are no devices of this type on this account %s",
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
                device["is_on"],
                device["connected"],
                device["model"],
            )
        )

        _LOGGER.info(
            "Adding DIO Chacon SWITCH with id %s, name %s, is_on %s, and connected %s",
            device["id"],
            device["name"],
            device["is_on"],
            device["connected"],
        )

    async_add_entities(device_list)


class DioChaconShade(RestoreEntity, SwitchEntity):
    """Object for controlling a Dio Chacon switch."""

    _attr_should_poll = False
    _attr_assumed_state = True
    _attr_has_entity_name = False

    def __init__(
        self, dio_chacon_client, target_id, name, is_on, connected, model
    ) -> None:
        """Initialize the switch."""
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
        """Turn on the switch."""

        _LOGGER.debug("Turn on the switch %s , %s", self._target_id, self._attr_name)

        await self.dio_chacon_client.switch_switch(self._target_id, True)

        # Effective state received via callback _on_device_state_changed

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""

        _LOGGER.debug("Turn off the switch %s , %s", self._target_id, self._attr_name)

        await self.dio_chacon_client.switch_switch(self._target_id, False)

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
        self.schedule_update_ha_state(True)

    def _effectively_update_entity_state(self, data: dict[str, Any]) -> None:
        self._attr_available = data["connected"]
        is_on = data["is_on"]
        self._attr_is_on = is_on
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Get the latest data from the Dio Chacon API and update the states."""
        _LOGGER.debug(
            "Launching reload of switch device state for id %s, and name %s",
            self._target_id,
            self._attr_name,
        )
        data = await self.dio_chacon_client.get_status_details([self._target_id])
        details = data[self._target_id]
        self._effectively_update_entity_state(details)
