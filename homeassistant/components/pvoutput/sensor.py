"""Support for getting collected information from PVOutput."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pvo import Status, System
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
    CONF_API_KEY,
    CONF_NAME,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    POWER_KILO_WATT,
    POWER_WATT,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_EFFICIENCY,
    ATTR_ENERGY_CONSUMPTION,
    ATTR_ENERGY_GENERATION,
    ATTR_POWER_CONSUMPTION,
    ATTR_POWER_GENERATION,
    CONF_SYSTEM_ID,
    DEFAULT_NAME,
    DOMAIN,
    LOGGER,
)
from .coordinator import PVOutputDataUpdateCoordinator

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_SYSTEM_ID): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


@dataclass
class PVOutputSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Status], int | float | None]


@dataclass
class PVOutputSensorEntityDescription(
    SensorEntityDescription, PVOutputSensorEntityDescriptionMixin
):
    """Describes a PVOutput sensor entity."""


SENSORS: tuple[PVOutputSensorEntityDescription, ...] = (
    PVOutputSensorEntityDescription(
        key="energy_consumption",
        name="Energy Consumed",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda status: status.energy_consumption,
    ),
    PVOutputSensorEntityDescription(
        key="energy_generation",
        name="Energy Generated",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda status: status.energy_generation,
    ),
    PVOutputSensorEntityDescription(
        key="normalized_output",
        name="Efficiency",
        native_unit_of_measurement=f"{ENERGY_KILO_WATT_HOUR}/{POWER_KILO_WATT}",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.normalized_output,
    ),
    PVOutputSensorEntityDescription(
        key="power_consumption",
        name="Power Consumed",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.power_consumption,
    ),
    PVOutputSensorEntityDescription(
        key="power_generation",
        name="Power Generated",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.power_generation,
    ),
    PVOutputSensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.temperature,
    ),
    PVOutputSensorEntityDescription(
        key="voltage",
        name="Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.voltage,
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the PVOutput sensor."""
    LOGGER.warning(
        "Configuration of the PVOutput platform in YAML is deprecated and will be "
        "removed in Home Assistant 2022.4; Your existing configuration "
        "has been imported into the UI automatically and can be safely removed "
        "from your configuration.yaml file"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_SYSTEM_ID: config[CONF_SYSTEM_ID],
                CONF_API_KEY: config[CONF_API_KEY],
                CONF_NAME: config[CONF_NAME],
            },
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a PVOutput sensors based on a config entry."""
    coordinator: PVOutputDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    system = await coordinator.pvoutput.system()

    async_add_entities(
        PVOutputSensorEntity(
            coordinator=coordinator,
            description=description,
            system_id=entry.data[CONF_SYSTEM_ID],
            system=system,
        )
        for description in SENSORS
    )


class PVOutputSensorEntity(CoordinatorEntity, SensorEntity):
    """Representation of a PVOutput sensor."""

    coordinator: PVOutputDataUpdateCoordinator
    entity_description: PVOutputSensorEntityDescription

    def __init__(
        self,
        *,
        coordinator: PVOutputDataUpdateCoordinator,
        description: PVOutputSensorEntityDescription,
        system_id: str,
        system: System,
    ) -> None:
        """Initialize a PVOutput sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{system_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            configuration_url=f"https://pvoutput.org/list.jsp?sid={system_id}",
            identifiers={(DOMAIN, str(system_id))},
            manufacturer="PVOutput",
            model=system.inverter_brand,
            name=system.system_name,
        )

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the device."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, int | float | None] | None:
        """Return the state attributes of the monitored installation."""

        # Only add attributes to the original sensor
        if self.entity_description.key != "energy_generation":
            return None

        return {
            ATTR_ENERGY_GENERATION: self.coordinator.data.energy_generation,
            ATTR_POWER_GENERATION: self.coordinator.data.power_generation,
            ATTR_ENERGY_CONSUMPTION: self.coordinator.data.energy_consumption,
            ATTR_POWER_CONSUMPTION: self.coordinator.data.power_consumption,
            ATTR_EFFICIENCY: self.coordinator.data.normalized_output,
            ATTR_TEMPERATURE: self.coordinator.data.temperature,
            ATTR_VOLTAGE: self.coordinator.data.voltage,
        }
