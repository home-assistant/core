"""Support for Fritzbox binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_WINDOW,
    BinarySensorEntity,
)
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FritzBoxEntity
from .const import CONF_COORDINATOR, DOMAIN as FRITZBOX_DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the FRITZ!SmartHome binary sensor from ConfigEntry."""
    entities: list[FritzboxBinarySensor] = []
    coordinator = hass.data[FRITZBOX_DOMAIN][entry.entry_id][CONF_COORDINATOR]

    for ain, device in coordinator.data.items():
        if not device.has_alarm:
            continue

        entities.append(
            FritzboxBinarySensor(
                {
                    ATTR_NAME: f"{device.name}",
                    ATTR_ENTITY_ID: f"{device.ain}",
                    ATTR_UNIT_OF_MEASUREMENT: None,
                    ATTR_DEVICE_CLASS: DEVICE_CLASS_WINDOW,
                    ATTR_STATE_CLASS: None,
                },
                coordinator,
                ain,
            )
        )

    async_add_entities(entities)


class FritzboxBinarySensor(FritzBoxEntity, BinarySensorEntity):
    """Representation of a binary FRITZ!SmartHome device."""

    @property
    def is_on(self) -> bool:
        """Return true if sensor is on."""
        return self.device.alert_state  # type: ignore [no-any-return]
