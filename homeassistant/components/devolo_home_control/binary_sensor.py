"""Platform for binary sensor integration."""
from __future__ import annotations

from devolo_home_control_api.devices.zwave import Zwave
from devolo_home_control_api.homecontrol import HomeControl

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_HEAT,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_PROBLEM,
    DEVICE_CLASS_SAFETY,
    DEVICE_CLASS_SMOKE,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .devolo_device import DevoloDeviceEntity

DEVICE_CLASS_MAPPING = {
    "Water alarm": DEVICE_CLASS_MOISTURE,
    "Home Security": DEVICE_CLASS_MOTION,
    "Smoke Alarm": DEVICE_CLASS_SMOKE,
    "Heat Alarm": DEVICE_CLASS_HEAT,
    "door": DEVICE_CLASS_DOOR,
    "overload": DEVICE_CLASS_SAFETY,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Get all binary sensor and multi level sensor devices and setup them via config entry."""
    entities: list[BinarySensorEntity] = []

    for gateway in hass.data[DOMAIN][entry.entry_id]["gateways"]:
        for device in gateway.binary_sensor_devices:
            for binary_sensor in device.binary_sensor_property:
                entities.append(
                    DevoloBinaryDeviceEntity(
                        homecontrol=gateway,
                        device_instance=device,
                        element_uid=binary_sensor,
                    )
                )
        for device in gateway.devices.values():
            if hasattr(device, "remote_control_property"):
                for remote in device.remote_control_property:
                    for index in range(
                        1, device.remote_control_property[remote].key_count + 1
                    ):
                        entities.append(
                            DevoloRemoteControl(
                                homecontrol=gateway,
                                device_instance=device,
                                element_uid=remote,
                                key=index,
                            )
                        )
    async_add_entities(entities, False)


class DevoloBinaryDeviceEntity(DevoloDeviceEntity, BinarySensorEntity):
    """Representation of a binary sensor within devolo Home Control."""

    def __init__(
        self, homecontrol: HomeControl, device_instance: Zwave, element_uid: str
    ) -> None:
        """Initialize a devolo binary sensor."""
        self._binary_sensor_property = device_instance.binary_sensor_property.get(
            element_uid
        )

        super().__init__(
            homecontrol=homecontrol,
            device_instance=device_instance,
            element_uid=element_uid,
        )

        self._attr_device_class = DEVICE_CLASS_MAPPING.get(
            self._binary_sensor_property.sub_type
            or self._binary_sensor_property.sensor_type
        )

        if self._attr_device_class is None:
            if device_instance.binary_sensor_property.get(element_uid).sub_type != "":
                self._attr_name += f" {device_instance.binary_sensor_property.get(element_uid).sub_type}"
            else:
                self._attr_name += f" {device_instance.binary_sensor_property.get(element_uid).sensor_type}"

        self._value = self._binary_sensor_property.state

        if element_uid.startswith("devolo.WarningBinaryFI:"):
            self._attr_device_class = DEVICE_CLASS_PROBLEM
            self._attr_entity_registry_enabled_default = False

    @property
    def is_on(self) -> bool:
        """Return the state."""
        return bool(self._value)


class DevoloRemoteControl(DevoloDeviceEntity, BinarySensorEntity):
    """Representation of a remote control within devolo Home Control."""

    def __init__(
        self,
        homecontrol: HomeControl,
        device_instance: Zwave,
        element_uid: str,
        key: int,
    ) -> None:
        """Initialize a devolo remote control."""
        self._remote_control_property = device_instance.remote_control_property.get(
            element_uid
        )

        super().__init__(
            homecontrol=homecontrol,
            device_instance=device_instance,
            element_uid=f"{element_uid}_{key}",
        )

        self._key = key
        self._attr_is_on = False

    def _sync(self, message: tuple) -> None:
        """Update the binary sensor state."""
        if (
            message[0] == self._remote_control_property.element_uid
            and message[1] == self._key
        ):
            self._attr_is_on = True
        elif (
            message[0] == self._remote_control_property.element_uid and message[1] == 0
        ):
            self._attr_is_on = False
        else:
            self._generic_message(message)
        self.schedule_update_ha_state()
