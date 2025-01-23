"""Support for Palazzetti sensors."""

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfLength, UnitOfMass, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import PalazzettiConfigEntry
from .const import STATUS_TO_HA
from .coordinator import PalazzettiDataUpdateCoordinator
from .entity import PalazzettiEntity


@dataclass(frozen=True, kw_only=True)
class PropertySensorEntityDescription(SensorEntityDescription):
    """Describes a Palazzetti sensor entity that is read from a `PalazzettiClient` property."""

    client_property: str
    property_map: dict[StateType, str] | None = None
    presence_flag: None | str = None


PROPERTY_SENSOR_DESCRIPTIONS: list[PropertySensorEntityDescription] = [
    PropertySensorEntityDescription(
        key="status",
        device_class=SensorDeviceClass.ENUM,
        translation_key="status",
        client_property="status",
        property_map=STATUS_TO_HA,
        options=list(STATUS_TO_HA.values()),
    ),
    PropertySensorEntityDescription(
        key="pellet_quantity",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="pellet_quantity",
        client_property="pellet_quantity",
    ),
    PropertySensorEntityDescription(
        key="pellet_level",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="pellet_level",
        presence_flag="has_pellet_level",
        client_property="pellet_level",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PalazzettiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Palazzetti sensor entities based on a config entry."""

    coordinator = entry.runtime_data

    sensors = [
        PalazzettiSensor(
            coordinator,
            PropertySensorEntityDescription(
                key=sensor.description_key.value,
                device_class=SensorDeviceClass.TEMPERATURE,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                state_class=SensorStateClass.MEASUREMENT,
                translation_key=sensor.description_key.value,
                client_property=sensor.state_property,
            ),
        )
        for sensor in coordinator.client.list_temperatures()
    ]

    sensors.extend(
        [
            PalazzettiSensor(coordinator, description)
            for description in PROPERTY_SENSOR_DESCRIPTIONS
            if not description.presence_flag
            or getattr(coordinator.client, description.presence_flag)
        ]
    )

    if sensors:
        async_add_entities(sensors)


class PalazzettiSensor(PalazzettiEntity, SensorEntity):
    """Define a Palazzetti sensor."""

    entity_description: PropertySensorEntityDescription

    def __init__(
        self,
        coordinator: PalazzettiDataUpdateCoordinator,
        description: PropertySensorEntityDescription,
    ) -> None:
        """Initialize Palazzetti sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}-{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state value of the sensor."""

        raw_value = getattr(
            self.coordinator.client, self.entity_description.client_property
        )

        if self.entity_description.property_map:
            return self.entity_description.property_map[raw_value]

        return raw_value
