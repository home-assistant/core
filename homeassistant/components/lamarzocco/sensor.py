"""Sensor platform for La Marzocco espresso machines."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MODEL_GS3_AV, MODEL_GS3_MP, MODEL_LM, MODEL_LMU
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription
from .lm_client import LaMarzoccoClient

DRINKS = "drinks"
CONTINUOUS = "continuous"
TOTAL_COFFEE = "total_coffee"
TOTAL_FLUSHING = "total_flushing"

ATTR_MAP_DRINK_STATS_GS3_AV = [
    (DRINKS, "k1"),
    (DRINKS, "k2"),
    (DRINKS, "k3"),
    (DRINKS, "k4"),
    CONTINUOUS,
    TOTAL_FLUSHING,
    TOTAL_COFFEE,
]

ATTR_MAP_DRINK_STATS_GS3_MP_LM = [
    (DRINKS, "k1"),
    TOTAL_FLUSHING,
    TOTAL_COFFEE,
]


@dataclass
class LaMarzoccoSensorEntityDescriptionMixin:
    """Description of an La Marzocco Sensor."""

    available_fn: Callable[[LaMarzoccoClient], bool]
    value_fn: Callable[[LaMarzoccoClient], float | int]


@dataclass
class LaMarzoccoSensorEntityDescription(
    SensorEntityDescription,
    LaMarzoccoEntityDescription,
    LaMarzoccoSensorEntityDescriptionMixin,
):
    """Description of an La Marzocco Sensor."""


ENTITIES: tuple[LaMarzoccoSensorEntityDescription, ...] = (
    LaMarzoccoSensorEntityDescription(
        key="drink_stats",
        translation_key="drink_stats",
        icon="mdi:chart-line",
        native_unit_of_measurement="drinks",
        state_class=SensorStateClass.MEASUREMENT,
        available_fn=lambda client: all(
            client.current_status.get(p) is not None
            for p in ("drinks_k1", "total_flushing")
        ),
        value_fn=lambda client: sum(
            client.current_status.get(p, 0) for p in ("drinks_k1", "total_flushing")
        ),
        extra_attributes={
            MODEL_GS3_AV: ATTR_MAP_DRINK_STATS_GS3_AV,
            MODEL_GS3_MP: ATTR_MAP_DRINK_STATS_GS3_MP_LM,
            MODEL_LM: ATTR_MAP_DRINK_STATS_GS3_MP_LM,
            MODEL_LMU: ATTR_MAP_DRINK_STATS_GS3_MP_LM,
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        LaMarzoccoSensorEntity(coordinator, hass, description)
        for description in ENTITIES
        if not description.extra_attributes
        or coordinator.lm.model_name in description.extra_attributes
    )


class LaMarzoccoSensorEntity(LaMarzoccoEntity, SensorEntity):
    """Sensor representing espresso machine temperature data."""

    entity_description: LaMarzoccoSensorEntityDescription

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        return self.entity_description.available_fn(self._lm_client)

    @property
    def native_value(self) -> int | float:
        """State of the sensor."""
        return self.entity_description.value_fn(self._lm_client)
