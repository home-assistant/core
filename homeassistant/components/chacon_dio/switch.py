"""Switch Platform for Chacon Dio REV-LIGHT and switch plug devices."""

import logging
from typing import Any

from dio_chacon_wifi_api.const import DeviceTypeEnum

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ChaconDioConfigEntry
from .entity import ChaconDioEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ChaconDioConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Chacon Dio switch devices."""
    data = config_entry.runtime_data
    client = data.client

    async_add_entities(
        ChaconDioSwitch(client, device)
        for device in data.list_devices
        if device["type"]
        in (DeviceTypeEnum.SWITCH_LIGHT.value, DeviceTypeEnum.SWITCH_PLUG.value)
    )


class ChaconDioSwitch(ChaconDioEntity, SwitchEntity):
    """Object for controlling a Chacon Dio switch."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_name = None

    def _update_attr(self, data: dict[str, Any]) -> None:
        """Recomputes the attributes values either at init or when the device state changes."""
        self._attr_available = data["connected"]
        self._attr_is_on = data["is_on"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch.

        Turned on status is effective after the server callback that triggers callback_device_state.
        """

        _LOGGER.debug(
            "Turn on the switch %s , %s, %s",
            self.target_id,
            self.entity_id,
            self._attr_is_on,
        )

        await self.client.switch_switch(self.target_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch.

        Turned on status is effective after the server callback that triggers callback_device_state.
        """

        _LOGGER.debug(
            "Turn off the switch %s , %s, %s",
            self.target_id,
            self.entity_id,
            self._attr_is_on,
        )

        await self.client.switch_switch(self.target_id, False)
