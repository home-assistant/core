"""This platform provides binary sensors for key RainMachine data."""
from dataclasses import dataclass
from functools import partial

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RainMachineEntity
from .const import (
    DATA_CONTROLLER,
    DATA_COORDINATOR,
    DATA_PROVISION_SETTINGS,
    DATA_RESTRICTIONS_CURRENT,
    DATA_RESTRICTIONS_UNIVERSAL,
    DOMAIN,
)
from .model import RainMachineSensorDescriptionMixin

TYPE_FLOW_SENSOR = "flow_sensor"
TYPE_FREEZE = "freeze"
TYPE_FREEZE_PROTECTION = "freeze_protection"
TYPE_HOT_DAYS = "extra_water_on_hot_days"
TYPE_HOURLY = "hourly"
TYPE_MONTH = "month"
TYPE_RAINDELAY = "raindelay"
TYPE_RAINSENSOR = "rainsensor"
TYPE_WEEKDAY = "weekday"


@dataclass
class RainMachineBinarySensorDescription(
    BinarySensorEntityDescription, RainMachineSensorDescriptionMixin
):
    """Describe a RainMachine binary sensor."""


BINARY_SENSOR_DESCRIPTIONS = (
    RainMachineBinarySensorDescription(
        key=TYPE_FLOW_SENSOR,
        name="Flow Sensor",
        icon="mdi:water-pump",
        api_category=DATA_PROVISION_SETTINGS,
    ),
    RainMachineBinarySensorDescription(
        key=TYPE_FREEZE,
        name="Freeze Restrictions",
        icon="mdi:cancel",
        api_category=DATA_RESTRICTIONS_CURRENT,
    ),
    RainMachineBinarySensorDescription(
        key=TYPE_FREEZE_PROTECTION,
        name="Freeze Protection",
        icon="mdi:weather-snowy",
        api_category=DATA_RESTRICTIONS_UNIVERSAL,
    ),
    RainMachineBinarySensorDescription(
        key=TYPE_HOT_DAYS,
        name="Extra Water on Hot Days",
        icon="mdi:thermometer-lines",
        api_category=DATA_RESTRICTIONS_UNIVERSAL,
    ),
    RainMachineBinarySensorDescription(
        key=TYPE_HOURLY,
        name="Hourly Restrictions",
        icon="mdi:cancel",
        entity_registry_enabled_default=False,
        api_category=DATA_RESTRICTIONS_CURRENT,
    ),
    RainMachineBinarySensorDescription(
        key=TYPE_MONTH,
        name="Month Restrictions",
        icon="mdi:cancel",
        entity_registry_enabled_default=False,
        api_category=DATA_RESTRICTIONS_CURRENT,
    ),
    RainMachineBinarySensorDescription(
        key=TYPE_RAINDELAY,
        name="Rain Delay Restrictions",
        icon="mdi:cancel",
        entity_registry_enabled_default=False,
        api_category=DATA_RESTRICTIONS_CURRENT,
    ),
    RainMachineBinarySensorDescription(
        key=TYPE_RAINSENSOR,
        name="Rain Sensor Restrictions",
        icon="mdi:cancel",
        entity_registry_enabled_default=False,
        api_category=DATA_RESTRICTIONS_CURRENT,
    ),
    RainMachineBinarySensorDescription(
        key=TYPE_WEEKDAY,
        name="Weekday Restrictions",
        icon="mdi:cancel",
        entity_registry_enabled_default=False,
        api_category=DATA_RESTRICTIONS_CURRENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up RainMachine binary sensors based on a config entry."""
    controller = hass.data[DOMAIN][DATA_CONTROLLER][entry.entry_id]
    coordinators = hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id]

    @callback
    def async_get_sensor(api_category: str) -> partial:
        """Generate the appropriate sensor object for an API category."""
        if api_category == DATA_PROVISION_SETTINGS:
            return partial(
                ProvisionSettingsBinarySensor,
                coordinators[DATA_PROVISION_SETTINGS],
            )

        if api_category == DATA_RESTRICTIONS_CURRENT:
            return partial(
                CurrentRestrictionsBinarySensor,
                coordinators[DATA_RESTRICTIONS_CURRENT],
            )

        return partial(
            UniversalRestrictionsBinarySensor,
            coordinators[DATA_RESTRICTIONS_UNIVERSAL],
        )

    async_add_entities(
        [
            async_get_sensor(description.api_category)(controller, description)
            for description in BINARY_SENSOR_DESCRIPTIONS
        ]
    )


class CurrentRestrictionsBinarySensor(RainMachineEntity, BinarySensorEntity):
    """Define a binary sensor that handles current restrictions data."""

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        if self.entity_description.key == TYPE_FREEZE:
            self._attr_is_on = self.coordinator.data["freeze"]
        elif self.entity_description.key == TYPE_HOURLY:
            self._attr_is_on = self.coordinator.data["hourly"]
        elif self.entity_description.key == TYPE_MONTH:
            self._attr_is_on = self.coordinator.data["month"]
        elif self.entity_description.key == TYPE_RAINDELAY:
            self._attr_is_on = self.coordinator.data["rainDelay"]
        elif self.entity_description.key == TYPE_RAINSENSOR:
            self._attr_is_on = self.coordinator.data["rainSensor"]
        elif self.entity_description.key == TYPE_WEEKDAY:
            self._attr_is_on = self.coordinator.data["weekDay"]


class ProvisionSettingsBinarySensor(RainMachineEntity, BinarySensorEntity):
    """Define a binary sensor that handles provisioning data."""

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        if self.entity_description.key == TYPE_FLOW_SENSOR:
            self._attr_is_on = self.coordinator.data["system"].get("useFlowSensor")


class UniversalRestrictionsBinarySensor(RainMachineEntity, BinarySensorEntity):
    """Define a binary sensor that handles universal restrictions data."""

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        if self.entity_description.key == TYPE_FREEZE_PROTECTION:
            self._attr_is_on = self.coordinator.data["freezeProtectEnabled"]
        elif self.entity_description.key == TYPE_HOT_DAYS:
            self._attr_is_on = self.coordinator.data["hotDaysExtraWatering"]
