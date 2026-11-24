"""Binary sensors for key RainMachine data."""

from dataclasses import dataclass
from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RainMachineConfigEntry
from .const import DATA_PROVISION_SETTINGS, DATA_RESTRICTIONS_CURRENT
from .entity import RainMachineEntity, RainMachineEntityDescription
from .util import key_exists

TYPE_FLOW_SENSOR = "flow_sensor"
TYPE_FREEZE = "freeze"
TYPE_HOURLY = "hourly"
TYPE_MONTH = "month"
TYPE_RAINDELAY = "raindelay"
TYPE_RAINSENSOR = "rainsensor"
TYPE_WEEKDAY = "weekday"


@dataclass(frozen=True, kw_only=True)
class RainMachineBinarySensorDescription(
    BinarySensorEntityDescription, RainMachineEntityDescription
):
    """Describe a RainMachine binary sensor."""

    data_key: str


BINARY_SENSOR_DESCRIPTIONS = (
    RainMachineBinarySensorDescription(
        key=TYPE_FLOW_SENSOR,
        translation_key=TYPE_FLOW_SENSOR,
        api_category=DATA_PROVISION_SETTINGS,
        data_key="useFlowSensor",
    ),
    RainMachineBinarySensorDescription(
        key=TYPE_FREEZE,
        translation_key=TYPE_FREEZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        api_category=DATA_RESTRICTIONS_CURRENT,
        data_key="freeze",
    ),
    RainMachineBinarySensorDescription(
        key=TYPE_HOURLY,
        translation_key=TYPE_HOURLY,
        entity_category=EntityCategory.DIAGNOSTIC,
        api_category=DATA_RESTRICTIONS_CURRENT,
        data_key="hourly",
    ),
    RainMachineBinarySensorDescription(
        key=TYPE_MONTH,
        translation_key=TYPE_MONTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        api_category=DATA_RESTRICTIONS_CURRENT,
        data_key="month",
    ),
    RainMachineBinarySensorDescription(
        key=TYPE_RAINDELAY,
        translation_key=TYPE_RAINDELAY,
        entity_category=EntityCategory.DIAGNOSTIC,
        api_category=DATA_RESTRICTIONS_CURRENT,
        data_key="rainDelay",
    ),
    RainMachineBinarySensorDescription(
        key=TYPE_RAINSENSOR,
        translation_key=TYPE_RAINSENSOR,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        api_category=DATA_RESTRICTIONS_CURRENT,
        data_key="rainSensor",
    ),
    RainMachineBinarySensorDescription(
        key=TYPE_WEEKDAY,
        translation_key=TYPE_WEEKDAY,
        entity_category=EntityCategory.DIAGNOSTIC,
        api_category=DATA_RESTRICTIONS_CURRENT,
        data_key="weekDay",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RainMachineConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up RainMachine binary sensors based on a config entry."""
    data = entry.runtime_data

    api_category_sensor_map = {
        DATA_PROVISION_SETTINGS: ProvisionSettingsBinarySensor,
        DATA_RESTRICTIONS_CURRENT: CurrentRestrictionsBinarySensor,
    }

    async_add_entities(
        api_category_sensor_map[description.api_category](entry, data, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
        if (
            (coordinator := data.coordinators[description.api_category]) is not None
            and coordinator.data
            and key_exists(coordinator.data, description.data_key)
        )
    )


class CurrentRestrictionsBinarySensor(RainMachineEntity, BinarySensorEntity):
    """Define a binary sensor that handles current restrictions data."""

    entity_description: RainMachineBinarySensorDescription

    @callback
    @override
    def update_from_latest_data(self) -> None:
        """Update the state."""
        if self.entity_description.key == TYPE_FREEZE:
            self._attr_is_on = self.coordinator.data.get("freeze")
        elif self.entity_description.key == TYPE_HOURLY:
            self._attr_is_on = self.coordinator.data.get("hourly")
        elif self.entity_description.key == TYPE_MONTH:
            self._attr_is_on = self.coordinator.data.get("month")
        elif self.entity_description.key == TYPE_RAINDELAY:
            self._attr_is_on = self.coordinator.data.get("rainDelay")
        elif self.entity_description.key == TYPE_RAINSENSOR:
            self._attr_is_on = self.coordinator.data.get("rainSensor")
        elif self.entity_description.key == TYPE_WEEKDAY:
            self._attr_is_on = self.coordinator.data.get("weekDay")


class ProvisionSettingsBinarySensor(RainMachineEntity, BinarySensorEntity):
    """Define a binary sensor that handles provisioning data."""

    entity_description: RainMachineBinarySensorDescription

    @callback
    @override
    def update_from_latest_data(self) -> None:
        """Update the state."""
        if self.entity_description.key == TYPE_FLOW_SENSOR:
            self._attr_is_on = self.coordinator.data.get("system", {}).get(
                "useFlowSensor"
            )
