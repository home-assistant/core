"""Platform for switch integration."""
from __future__ import annotations

from typing import Any

from devolo_home_control_api.devices.zwave import Zwave
from devolo_home_control_api.homecontrol import HomeControl

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .devolo_device import DevoloDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Get all devices and setup the switch devices via config entry."""
    entities = []

    for gateway in hass.data[DOMAIN][entry.entry_id]["gateways"]:
        for device in gateway.binary_switch_devices:
            for binary_switch in device.binary_switch_property:
                # Exclude the binary switch which also has multi_level_switches here,
                # because those are implemented as light entities now.
                if not hasattr(device, "multi_level_switch_property"):
                    entities.append(
                        DevoloSwitch(
                            homecontrol=gateway,
                            device_instance=device,
                            element_uid=binary_switch,
                        )
                    )

    async_add_entities(entities)


class DevoloSwitch(DevoloDeviceEntity, SwitchEntity):
    """Representation of a switch."""

    _attr_name = None

    def __init__(
        self, homecontrol: HomeControl, device_instance: Zwave, element_uid: str
    ) -> None:
        """Initialize an devolo Switch."""
        super().__init__(
            homecontrol=homecontrol,
            device_instance=device_instance,
            element_uid=element_uid,
        )
        self._binary_switch_property = self._device_instance.binary_switch_property[
            self._attr_unique_id  # type: ignore[index]
        ]
        self._attr_is_on = self._binary_switch_property.state

    def turn_on(self, **kwargs: Any) -> None:
        """Switch on the device."""
        self._binary_switch_property.set(state=True)

    def turn_off(self, **kwargs: Any) -> None:
        """Switch off the device."""
        self._binary_switch_property.set(state=False)

    def _sync(self, message: tuple) -> None:
        """Update the binary switch state and consumption."""
        if message[0].startswith("devolo.BinarySwitch"):
            self._attr_is_on = self._device_instance.binary_switch_property[
                message[0]
            ].state
        else:
            self._generic_message(message)
        self.schedule_update_ha_state()
