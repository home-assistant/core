"""Binary sensors for the Whirlpool Appliances integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from whirlpool.appliance import Appliance
from whirlpool.oven import Cavity, Oven

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WhirlpoolConfigEntry
from .entity import WhirlpoolEntity, WhirlpoolOvenEntity

SCAN_INTERVAL = timedelta(minutes=5)


@dataclass(frozen=True, kw_only=True)
class WhirlpoolBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Whirlpool binary sensor entity."""

    value_fn: Callable[[Appliance], bool | None]


WASHER_DRYER_SENSORS: list[WhirlpoolBinarySensorEntityDescription] = [
    WhirlpoolBinarySensorEntityDescription(
        key="door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda appliance: appliance.get_door_open(),
    )
]


@dataclass(frozen=True, kw_only=True)
class WhirlpoolOvenCavityBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Whirlpool oven cavity binary sensor entity."""

    value_fn: Callable[[Oven, Cavity], bool | None]


OVEN_CAVITY_SENSORS: list[WhirlpoolOvenCavityBinarySensorEntityDescription] = [
    WhirlpoolOvenCavityBinarySensorEntityDescription(
        key="oven_door",
        translation_key="oven_door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda oven, cavity: oven.get_door_opened(cavity),
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WhirlpoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Config flow entry for Whirlpool binary sensors."""
    entities: list = []
    appliances_manager = config_entry.runtime_data
    for washer_dryer in appliances_manager.washer_dryers:
        entities.extend(
            WhirlpoolBinarySensor(washer_dryer, description)
            for description in WASHER_DRYER_SENSORS
        )
    for oven in appliances_manager.ovens:
        cavities = []
        if oven.get_oven_cavity_exists(Cavity.Upper):
            cavities.append(Cavity.Upper)
        if oven.get_oven_cavity_exists(Cavity.Lower):
            cavities.append(Cavity.Lower)
        entities.extend(
            WhirlpoolOvenCavityBinarySensor(oven, cavity, description)
            for cavity in cavities
            for description in OVEN_CAVITY_SENSORS
        )
    async_add_entities(entities)


class WhirlpoolBinarySensor(WhirlpoolEntity, BinarySensorEntity):
    """A class for the Whirlpool binary sensors."""

    def __init__(
        self, appliance: Appliance, description: WhirlpoolBinarySensorEntityDescription
    ) -> None:
        """Initialize the washer sensor."""
        super().__init__(appliance, unique_id_suffix=f"-{description.key}")
        self.entity_description: WhirlpoolBinarySensorEntityDescription = description

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self._appliance)


class WhirlpoolOvenCavityBinarySensor(WhirlpoolOvenEntity, BinarySensorEntity):
    """A class for Whirlpool oven cavity binary sensors."""

    def __init__(
        self,
        oven: Oven,
        cavity: Cavity,
        description: WhirlpoolOvenCavityBinarySensorEntityDescription,
    ) -> None:
        """Initialize the oven cavity sensor."""
        super().__init__(oven)
        cavity_key_suffix = self.get_cavity_key_suffix(cavity)
        self.cavity = cavity
        self.entity_description: WhirlpoolOvenCavityBinarySensorEntityDescription = (
            description
        )
        self._attr_unique_id = f"{oven.said}_{description.key}{cavity_key_suffix}"
        self._attr_translation_key = f"{description.key}{cavity_key_suffix}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.oven, self.cavity)
