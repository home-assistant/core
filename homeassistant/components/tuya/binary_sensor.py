"""Support for Tuya binary sensors."""
from __future__ import annotations

from dataclasses import dataclass

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_SAFETY,
    DEVICE_CLASS_VIBRATION,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENTITY_CATEGORY_DIAGNOSTIC
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantTuyaData
from .base import TuyaEntity
from .const import DOMAIN, TUYA_DISCOVERY_NEW, DPCode


@dataclass
class TuyaBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Tuya binary sensor."""

    # DPCode, to use. If None, the key will be used as DPCode
    dpcode: DPCode | None = None

    # Value to consider binary sensor to be "on"
    on_value: bool | float | int | str = True


# All descriptions can be found here. Mostly the Boolean data types in the
# default status set of each category (that don't have a set instruction)
# end up being a binary sensor.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
BINARY_SENSORS: dict[str, tuple[TuyaBinarySensorEntityDescription, ...]] = {
    # Door Window Sensor
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf48hm02l8m
    "mcs": (
        TuyaBinarySensorEntityDescription(
            key=DPCode.DOORCONTACT_STATE,
            device_class=DEVICE_CLASS_DOOR,
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.TEMPER_ALARM,
            name="Tamper",
            entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        ),
    ),
    # Luminance Sensor
    # https://developer.tuya.com/en/docs/iot/categoryldcg?id=Kaiuz3n7u69l8
    "ldcg": (
        TuyaBinarySensorEntityDescription(
            key=DPCode.TEMPER_ALARM,
            name="Tamper",
            entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        ),
    ),
    # PIR Detector
    # https://developer.tuya.com/en/docs/iot/categorypir?id=Kaiuz3ss11b80
    "pir": (
        TuyaBinarySensorEntityDescription(
            key=DPCode.PIR,
            device_class=DEVICE_CLASS_MOTION,
            on_value="pir",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.TEMPER_ALARM,
            name="Tamper",
            entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        ),
    ),
    # Emergency Button
    # https://developer.tuya.com/en/docs/iot/categorysos?id=Kaiuz3oi6agjy
    "sos": (
        TuyaBinarySensorEntityDescription(
            key=DPCode.SOS_STATE,
            device_class=DEVICE_CLASS_SAFETY,
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.TEMPER_ALARM,
            name="Tamper",
            entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        ),
    ),
    # Vibration Sensor
    # https://developer.tuya.com/en/docs/iot/categoryzd?id=Kaiuz3a5vrzno
    "zd": (
        TuyaBinarySensorEntityDescription(
            key=f"{DPCode.SHOCK_STATE}_vibration",
            dpcode=DPCode.SHOCK_STATE,
            name="Vibration",
            device_class=DEVICE_CLASS_VIBRATION,
            on_value="vibration",
        ),
        TuyaBinarySensorEntityDescription(
            key=f"{DPCode.SHOCK_STATE}_drop",
            dpcode=DPCode.SHOCK_STATE,
            name="Drop",
            device_class=DEVICE_CLASS_VIBRATION,
            on_value="drop",
        ),
        TuyaBinarySensorEntityDescription(
            key=f"{DPCode.SHOCK_STATE}_tilt",
            dpcode=DPCode.SHOCK_STATE,
            name="Tilt",
            device_class=DEVICE_CLASS_VIBRATION,
            on_value="tilt",
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya binary sensor dynamically through Tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya binary sensor."""
        entities: list[TuyaBinarySensorEntity] = []
        for device_id in device_ids:
            device = hass_data.device_manager.device_map[device_id]
            if descriptions := BINARY_SENSORS.get(device.category):
                for description in descriptions:
                    dpcode = description.dpcode or description.key
                    if dpcode in device.status:
                        entities.append(
                            TuyaBinarySensorEntity(
                                device, hass_data.device_manager, description
                            )
                        )

        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaBinarySensorEntity(TuyaEntity, BinarySensorEntity):
    """Tuya Binary Sensor Entity."""

    entity_description: TuyaBinarySensorEntityDescription

    def __init__(
        self,
        device: TuyaDevice,
        device_manager: TuyaDeviceManager,
        description: TuyaBinarySensorEntityDescription,
    ) -> None:
        """Init Tuya binary sensor."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"

    @property
    def is_on(self) -> bool:
        """Return true if sensor is on."""
        dpcode = self.entity_description.dpcode or self.entity_description.key
        if dpcode not in self.device.status:
            return False
        return self.device.status[dpcode] == self.entity_description.on_value
