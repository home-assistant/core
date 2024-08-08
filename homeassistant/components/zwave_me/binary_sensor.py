"""Representation of a sensorBinary."""

from __future__ import annotations

from zwave_me_ws import ZWaveMeData

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ZWaveMeController, ZWaveMeEntity
from .const import DOMAIN, ZWaveMePlatform

BINARY_SENSORS_MAP: dict[str, BinarySensorEntityDescription] = {
    "generic": BinarySensorEntityDescription(
        key="generic",
    ),
    "motion": BinarySensorEntityDescription(
        key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
}
DEVICE_NAME = ZWaveMePlatform.BINARY_SENSOR


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""

    @callback
    def add_new_device(new_device: ZWaveMeData) -> None:
        controller: ZWaveMeController = hass.data[DOMAIN][config_entry.entry_id]
        description = BINARY_SENSORS_MAP.get(
            new_device.probeType, BINARY_SENSORS_MAP["generic"]
        )
        sensor = ZWaveMeBinarySensor(controller, new_device, description)

        async_add_entities(
            [
                sensor,
            ]
        )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"ZWAVE_ME_NEW_{DEVICE_NAME.upper()}", add_new_device
        )
    )


class ZWaveMeBinarySensor(ZWaveMeEntity, BinarySensorEntity):
    """Representation of a ZWaveMe binary sensor."""

    def __init__(
        self,
        controller: ZWaveMeController,
        device: ZWaveMeData,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the device."""
        super().__init__(controller=controller, device=device)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.device.level == "on"
