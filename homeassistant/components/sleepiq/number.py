"""Support for SleepIQ SleepNumber firmness number entities."""
from typing import List

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DATA_SLEEPIQ, SleepIQDataUpdateCoordinator, SleepIQEntity
from .const import (
    ACTUATOR,
    ATTRIBUTES,
    BED,
    FOOT,
    FOUNDATION,
    HEAD,
    NAME,
    RIGHT,
    SENSOR_TYPES,
    SIDES,
    SLEEP_NUMBER,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SleepIQ bed sensors."""
    coordinator = hass.data[DATA_SLEEPIQ].coordinators[config_entry.data[CONF_USERNAME]]
    entities = []

    for bed_id in coordinator.data:
        foundation_features = await hass.async_add_executor_job(
            coordinator.client.foundation_features
        )

        for side in SIDES:
            if getattr(coordinator.data[bed_id][BED], side) is not None:
                entities.append(SleepIQFirmnessNumber(coordinator, bed_id, side))

            # For split foundations, create head and foot actuators for each side
            if not foundation_features.single:
                entities.extend(
                    add_actuator_entities(
                        coordinator, bed_id, side, foundation_features
                    )
                )

        # For single foundations (not split), only create a one head and one foot actuator.
        # It doesn't matter which side is passed to the entity, either one will properly
        # control the actuators
        if foundation_features.single:
            entities.extend(
                add_actuator_entities(coordinator, bed_id, RIGHT, foundation_features)
            )

    async_add_entities(entities, True)


def add_actuator_entities(coordinator, bed_id, side, foundation_features) -> List:
    """Create head actuator entity, and foot actuator if the foundation has that capability."""
    entities = []
    entities.append(
        SleepIQFoundationActuator(
            coordinator, bed_id, side, HEAD, foundation_features.single
        )
    )
    if foundation_features.hasFootControl:
        entities.append(
            SleepIQFoundationActuator(
                coordinator, bed_id, side, FOOT, foundation_features.single
            )
        )

    return entities


class SleepIQFirmnessNumber(SleepIQEntity, NumberEntity):
    """Implementation of a SleepIQ Firmness number entity."""

    _attr_max_value: float = 100
    _attr_min_value: float = 5
    _attr_step: float = 5

    def __init__(
        self,
        coordinator: SleepIQDataUpdateCoordinator,
        bed_id: str,
        side: str,
    ) -> None:
        """Initialize the SleepIQ firmness number."""
        super().__init__(coordinator, bed_id, side)
        self._name = SLEEP_NUMBER
        self.client = coordinator.client

    @property
    def value(self) -> float:
        """Return the sleep number."""
        return self._side.sleep_number

    async def async_set_value(self, value: float) -> None:
        """Set new value."""
        if await self.hass.async_add_executor_job(
            self.client.set_sleepnumber, self.side, value, self.bed_id
        ):
            self._attr_value = value
            self.async_write_ha_state()


class SleepIQFoundationActuator(SleepIQEntity, NumberEntity):
    """Implementation of a SleepIQ foundation actuator."""

    _attr_max_value: float = 100
    _attr_min_value: float = 0
    _attr_step: float = 1

    def __init__(
        self,
        coordinator: SleepIQDataUpdateCoordinator,
        bed_id: str,
        side: str,
        actuator: str,
        single: bool,
    ) -> None:
        """Initialize the SleepIQ foundation actuator."""
        super().__init__(coordinator, bed_id, side)
        self._name = ACTUATOR if single else f"{side}_{ACTUATOR}"
        self.actuator = actuator
        self.client = coordinator.client
        self.single = single

    @property
    def _foundation(self) -> str:
        return self.coordinator.data[self.bed_id][FOUNDATION]

    @property
    def unique_id(self) -> str:
        """Return unique ID for the entity."""
        unique_id = f"{self.bed_id}_{self._side.sleeper.first_name}"
        if not self.single:
            unique_id += f"_{self.side}"
        return f"{unique_id}_{self.actuator}"

    @property
    def name(self) -> str:
        """Return name for the entity."""
        name = f"{NAME} {self._bed.name}"
        if not self.single:
            name += f" {self._side.sleeper.first_name}"
        return f"{name} {self.actuator} {SENSOR_TYPES[ACTUATOR]}"

    @property
    def value(self) -> float:
        """Return the foundation actuator position."""
        return getattr(self._foundation, ATTRIBUTES[self.side][self.actuator])

    async def async_set_value(self, value: float) -> None:
        """Set new value."""
        if await self.hass.async_add_executor_job(
            self.client.set_foundation_position,
            self.side,
            self.actuator,
            value,
            self.bed_id,
        ):
            self._attr_value = value
            self.async_write_ha_state()
