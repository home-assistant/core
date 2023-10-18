"""Binary Sensor platform for La Marzocco espresso machines."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BREW_ACTIVE, DOMAIN
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription
from .lm_client import LaMarzoccoClient


@dataclass
class LaMarzoccoBinarySensorEntityDescriptionMixin:
    """Description of an La Marzocco Binary Sensor."""

    is_on_fn: Callable[[LaMarzoccoClient], bool]


@dataclass
class LaMarzoccoBinarySensorEntityDescription(
    LaMarzoccoEntityDescription,
    BinarySensorEntityDescription,
    LaMarzoccoBinarySensorEntityDescriptionMixin,
):
    """Description of an La Marzocco Binary Sensor."""


ENTITIES: tuple[LaMarzoccoBinarySensorEntityDescription, ...] = (
    LaMarzoccoBinarySensorEntityDescription(
        key="water_reservoir",
        translation_key="water_reservoir",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:water-well",
        is_on_fn=lambda client: not client.current_status.get(
            "water_reservoir_contact"
        ),
        extra_attributes={},
    ),
    LaMarzoccoBinarySensorEntityDescription(
        key=BREW_ACTIVE,
        translation_key=BREW_ACTIVE,
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:cup-water",
        is_on_fn=lambda client: client.current_status.get(BREW_ACTIVE),
        extra_attributes={},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        LaMarzoccoBinarySensorEntity(coordinator, hass, description)
        for description in ENTITIES
        if not description.extra_attributes
        or coordinator.lm.model_name in description.extra_attributes
    )


class LaMarzoccoBinarySensorEntity(LaMarzoccoEntity, BinarySensorEntity):
    """Binary Sensor representing espresso machine water reservoir status."""

    entity_description: LaMarzoccoBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self._lm_client)
