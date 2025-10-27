"""Support for EnOcean binary sensors."""

from __future__ import annotations

from home_assistant_enocean.enocean_device_type import EnOceanDeviceType
from home_assistant_enocean.enocean_id import EnOceanID
from home_assistant_enocean.gateway import EnOceanHomeAssistantGateway

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .config_entry import EnOceanConfigEntry
from .entity import EnOceanEntity

DEFAULT_NAME = ""
DEPENDENCIES = ["enocean"]
EVENT_BUTTON_PRESSED = "button_pressed"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    # devices = config_entry.options.get(CONF_ENOCEAN_DEVICES, [])
    gateway = config_entry.runtime_data.gateway

    for enocean_id, entity_name in gateway.binary_sensor_entities:
        async_add_entities(
            [
                EnOceanBinarySensor(
                    enocean_id=enocean_id,
                    gateway=config_entry.runtime_data.gateway,
                    device_name="EnOcean Binary Sensor",
                    channel=entity_name,
                    name=entity_name,
                )
            ]
        )


class EnOceanBinarySensor(EnOceanEntity, BinarySensorEntity):
    """Representation of EnOcean binary sensors such as wall switches."""

    def __init__(
        self,
        enocean_id: EnOceanID,
        gateway: EnOceanHomeAssistantGateway,
        device_name: str,
        device_class: BinarySensorDeviceClass | None = None,
        channel: str | None = None,
        dev_type: EnOceanDeviceType = EnOceanDeviceType(),
        name: str | None = None,
    ) -> None:
        """Initialize the EnOcean binary sensor."""
        super().__init__(
            enocean_id=enocean_id,
            gateway=gateway,
            device_name=device_name,
            device_type=dev_type,
            name=name,
        )
        self._attr_device_class = device_class
        self._channel = channel

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the class of this sensor."""
        return self._attr_device_class

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        is_on: bool | None = self.gateway.binary_sensor_is_on(
            enocean_id=self.enocean_id, name=self._channel
        )
        return is_on
