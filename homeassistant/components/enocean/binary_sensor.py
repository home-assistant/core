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
from .config_flow import CONF_ENOCEAN_DEVICE_TYPE_ID, CONF_ENOCEAN_DEVICES
from .const import ENOCEAN_BINARY_SENSOR_EEPS
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

    async_add_entities(
        [
            EnOceanBinarySensor(
                enocean_id=config_entry.runtime_data.gateway.chip_id,
                gateway=config_entry.runtime_data.gateway,
                device_name="EnOcean Gateway",
                name="Teach-In Active",
                dev_type=EnOceanDeviceType(
                    manufacturer="EnOcean", model="TCM300/310 Transmitter", eep=""
                ),
            )
        ]
    )

    devices = config_entry.options.get(CONF_ENOCEAN_DEVICES, [])

    for device in devices:
        device_type_id = device[CONF_ENOCEAN_DEVICE_TYPE_ID]
        device_type = EnOceanDeviceType.get_supported_device_types()[device_type_id]
        eep = device_type.eep

        if eep in ENOCEAN_BINARY_SENSOR_EEPS:
            device_id = EnOceanID(device["id"])

            async_add_entities(
                [
                    EnOceanBinarySensor(
                        enocean_id=device_id,
                        gateway=config_entry.runtime_data.gateway,
                        device_name=device["name"],
                        channel=channel,
                        dev_type=device_type,
                        name=channel,
                    )
                    for channel in (
                        "A0",
                        "A1",
                        "B0",
                        "B1",
                        "AB0",
                        "AB1",
                        "A0B1",
                        "A1B0",
                    )
                ]
            )


class EnOceanBinarySensor(EnOceanEntity, BinarySensorEntity):
    """Representation of EnOcean binary sensors such as wall switches.

    Supported EEPs (EnOcean Equipment Profiles):
    - F6-02-01 (Light and Blind Control - Application Style 2)
    - F6-02-02 (Light and Blind Control - Application Style 1)
    """

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
        is_on = False
        if self.gateway.binary_sensor_is_on(self.enocean_id, self._channel):
            is_on = True
        return is_on
