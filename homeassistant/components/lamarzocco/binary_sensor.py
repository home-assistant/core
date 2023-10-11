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

from .const import (
    BREW_ACTIVE,
    CONF_USE_WEBSOCKET,
    DOMAIN,
    MODEL_GS3_AV,
    MODEL_GS3_MP,
    MODEL_LM,
    MODEL_LMU,
)
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription
from .lm_client import LaMarzoccoClient


@dataclass
class LaMarzoccoBinarySensorEntityDescriptionMixin:
    """Description of an La Marzocco Binary Sensor."""

    is_on_fn: Callable[[LaMarzoccoClient], bool]
    is_available_fn: Callable[[LaMarzoccoClient], bool]


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
        is_available_fn=lambda client: client.current_status.get(
            "water_reservoir_contact"
        )
        is not None,
        extra_attributes={
            MODEL_GS3_AV: None,
            MODEL_GS3_MP: None,
            MODEL_LM: None,
            MODEL_LMU: None,
        },
    ),
    LaMarzoccoBinarySensorEntityDescription(
        key=BREW_ACTIVE,
        translation_key=BREW_ACTIVE,
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:cup-water",
        is_on_fn=lambda client: client.current_status.get(BREW_ACTIVE),
        is_available_fn=lambda client: client.current_status.get(BREW_ACTIVE)
        is not None,
        extra_attributes={
            MODEL_GS3_AV: None,
            MODEL_GS3_MP: None,
            MODEL_LM: None,
            MODEL_LMU: None,
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    use_websocket = config_entry.options.get(CONF_USE_WEBSOCKET, True)

    entities = []
    for description in ENTITIES:
        if coordinator.lm.model_name in description.extra_attributes:
            if description.key == BREW_ACTIVE and not use_websocket:
                continue
            entities.append(
                LaMarzoccoBinarySensorEntity(coordinator, hass, description)
            )

    async_add_entities(entities)


class LaMarzoccoBinarySensorEntity(LaMarzoccoEntity, BinarySensorEntity):
    """Binary Sensor representing espresso machine water reservoir status."""

    entity_description: LaMarzoccoBinarySensorEntityDescription

    @property
    def available(self) -> bool:
        """Return if binary sensor is available."""
        return self.entity_description.is_available_fn(self._lm_client)

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self._lm_client)
