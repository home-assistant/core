"""SFR Box sensor platform."""
from sfrbox_api.bridge import SFRBox
from sfrbox_api.models import SystemInfo

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS, UnitOfDataRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DslDataUpdateCoordinator

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="linemode",
        name="Line mode",
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="counter",
        name="Counter",
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="crc",
        name="CRC",
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="status",
        name="Status",
        device_class=SensorDeviceClass.ENUM,
        options=["up", "down"],
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="noise_down",
        name="Noise down",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="noise_up",
        name="Noise up",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="attenuation_down",
        name="Attenuation down",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="attenuation_up",
        name="Attenuation up",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="rate_down",
        name="Rate down",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="rate_up",
        name="Rate up",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="line_status",
        name="Line status",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "No Defect",
            "Of Frame",
            "Loss Of Signal",
            "Loss Of Power",
            "Loss Of Signal Quality",
            "Unknown",
        ],
        has_entity_name=True,
    ),
    SensorEntityDescription(
        key="training",
        name="Training",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "Idle",
            "G.994 Training",
            "G.992 Started",
            "G.922 Channel Analysis",
            "G.992 Message Exchange",
            "G.993 Started",
            "G.993 Channel Analysis",
            "G.993 Message Exchange",
            "Showtime",
            "Unknown",
        ],
        has_entity_name=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    box: SFRBox = data["box"]
    system_info = await box.system_get_info()

    entities = [
        SFRBoxSensor(data["dsl_coordinator"], description, system_info)
        for description in SENSOR_TYPES
    ]
    async_add_entities(entities, True)


class SFRBoxSensor(CoordinatorEntity[DslDataUpdateCoordinator], SensorEntity):
    """SFR Box sensor."""

    def __init__(
        self,
        coordinator: DslDataUpdateCoordinator,
        description: SensorEntityDescription,
        system_info: SystemInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{system_info.mac_addr}_dsl_{description.key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, system_info.mac_addr)}}

    @property
    def native_value(self) -> StateType:
        """Return the native value of the device."""
        if self.coordinator.data is None:
            return None
        return getattr(self.coordinator.data, self.entity_description.key)
